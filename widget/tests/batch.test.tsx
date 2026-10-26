/** Firma en lote: enlaces, cliente del servidor, un solo certificado y PIN, resultado parcial y reintento. */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { describe, expect, it, vi } from "vitest";

import { App } from "../src/App";
import { ServerError } from "../src/api/errors";
import { batchToContext, createBatchServerClient } from "../src/api/serverClient";
import type { BatchContextResponse, BatchDocument, Challenge } from "../src/api/types";
import { linkFromPath } from "../src/bootstrap/token";
import { createHostNotifier } from "../src/embed/hostMessages";
import { jsonResponse, makeCert, makeFakes, TOKEN, type Fakes } from "./fixtures";

const NOW = new Date("2026-10-08T12:00:00Z");
const BATCH_ID = "aaaaaaaa-2222-4333-8444-555555555555";

function doc(i: number, overrides: Partial<BatchDocument> = {}): BatchDocument {
  return {
    signature_request_id: `req-${i}`,
    document_id: `doc-${i}`,
    document_name: `Expediente_${i}.pdf`,
    page_count: i + 1,
    size_bytes: 190 * 1024,
    status: "pending",
    version_number: null,
    error: null,
    ...overrides,
  };
}

function rawBatch(overrides: Partial<BatchContextResponse> = {}): BatchContextResponse {
  return {
    id: BATCH_ID,
    status: "pending",
    provider: "token",
    allowed_providers: ["token", "local"],
    signer_name: "María Fernanda Ríos",
    allowed_origins: ["https://gestor.example.org"],
    agent_url: "http://127.0.0.1:47123",
    token_expires_at: "2026-10-08T12:00:00Z",
    completed_at: null,
    documents: [doc(0), doc(1), doc(2)],
    ...overrides,
  };
}

const challenges = (n: number): Challenge[] =>
  Array.from({ length: n }, (_, i) => ({
    challenge_id: `ch-${i}`,
    document_name: `Expediente_${i}.pdf`,
    hash_algorithm: "SHA-256",
    hash_to_sign: `hash-${i}`,
  }));

function batchFakes(raw: BatchContextResponse = rawBatch()): Fakes {
  const context = batchToContext(raw);
  const fakes = makeFakes(context);
  fakes.server.prepare.mockResolvedValue({ challenges: challenges(raw.documents.length), expires_at: "2099-01-01T00:00:00Z" });
  fakes.agent.sign.mockResolvedValue(
    challenges(raw.documents.length).map((c) => ({ challenge_id: c.challenge_id, signature_base64: "U0lH" })),
  );
  return fakes;
}

function mount(fakes: Fakes) {
  return render(<App services={fakes.services} now={() => NOW} />);
}
const heading = (name: string | RegExp) => screen.findByRole("heading", { name, level: 1 });
const click = (name: string | RegExp) => userEvent.click(screen.getByRole("button", { name }));

describe("enlaces de lote", () => {
  const id = BATCH_ID;
  it("distingue una solicitud de un lote", () => {
    expect(linkFromPath(`/sign/batch/${id}`)).toEqual({ kind: "batch", id });
    expect(linkFromPath(`/sign/batch/${id}/`)).toEqual({ kind: "batch", id });
    expect(linkFromPath(`/sign/${id}`)).toEqual({ kind: "request", id });
  });
  it.each(["/sign/batch/no-es-uuid", "/sign/batch/", "/sign/batch", "/otra/ruta", `/sign/batch/${BATCH_ID}/x`])(
    "rechaza %s",
    (path) => expect(linkFromPath(path)).toBeNull(),
  );
});

describe("cliente de lote", () => {
  const client = (fetchFn: unknown) =>
    createBatchServerClient({ requestId: BATCH_ID, token: TOKEN, sessionRef: "s1", fetchFn: fetchFn as typeof fetch });

  it("usa las rutas de lote con el token en la cabecera y adapta el contexto", async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(rawBatch()));
    const context = await client(fetchFn).getContext();
    const [url, init] = fetchFn.mock.calls[0]!;
    expect(url).toBe(`/api/v1/widget/batches/${BATCH_ID}`);
    expect(url).not.toContain(TOKEN);
    expect(init.headers.Authorization).toBe(`Bearer ${TOKEN}`);
    expect(context.document_name).toBe("3 documentos");
    expect(context.status).toBe("pending");
    expect(context.batch?.documents).toHaveLength(3);
  });

  it("los estados terminales del lote llevan a la pantalla de resultado", () => {
    for (const status of ["completed", "partial_failure", "failed"]) {
      expect(batchToContext(rawBatch({ status })).status).toBe("signed");
    }
    expect(batchToContext(rawBatch({ status: "signing" })).status).toBe("signing");
  });

  it("prepare, complete, descarga y reintento", async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ challenges: challenges(3), expires_at: "2099-01-01T00:00:00Z" }))
      .mockResolvedValueOnce(jsonResponse(rawBatch({ status: "completed" })))
      .mockResolvedValueOnce(new Response("zip", { headers: { "content-disposition": 'attachment; filename="firmados.zip"' } }))
      .mockResolvedValueOnce(jsonResponse({ id: "otro", signing_url: "http://x/sign/batch/otro#t=nuevo" }, 201));
    const c = client(fetchFn);
    expect((await c.prepare("PEM")).challenges).toHaveLength(3);
    expect((await c.complete([{ challenge_id: "a", signature_base64: "b" }])).batch?.status).toBe("completed");
    expect((await c.downloadPdf()).filename).toBe("firmados.zip");
    expect((await c.retry!()).signing_url).toContain("/sign/batch/otro");
    expect(fetchFn.mock.calls.map((call) => call[0])).toEqual([
      `/api/v1/widget/batches/${BATCH_ID}/prepare`,
      `/api/v1/widget/batches/${BATCH_ID}/complete`,
      `/api/v1/widget/batches/${BATCH_ID}/download`,
      `/api/v1/widget/batches/${BATCH_ID}/retry`,
    ]);
  });

  it("una respuesta con otra forma se rechaza", async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ id: BATCH_ID }));
    await expect(client(fetchFn).getContext()).rejects.toMatchObject({ code: "invalid_response" });
  });
});

describe("revisión del lote", () => {
  it("lista los documentos y ofrece 'Firmar N documentos'", async () => {
    mount(batchFakes());
    await heading("Elegí el método de firma");
    const list = screen.getByRole("region", { name: "Documentos a firmar (3)" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(within(list).getByText("Expediente_1.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Firmar 3 documentos" })).toBeEnabled();
    expect(screen.getByText(/Un solo PIN para los 3 documentos/)).toBeInTheDocument();
  });

  it("la firma remota se muestra deshabilitada con su motivo", async () => {
    mount(batchFakes());
    await heading("Elegí el método de firma");
    expect(screen.getByRole("radio", { name: /Firma remota/ })).toBeDisabled();
    expect(screen.getByText(/Confirmás en el servicio de firma remota/)).toBeInTheDocument();
    expect(screen.getByText("No está disponible para firmar lotes.")).toBeInTheDocument();
  });

  it("con un solo método igual muestra la revisión con esa tarjeta elegida", async () => {
    mount(batchFakes(rawBatch({ provider: "local", allowed_providers: ["local"] })));
    await heading("Elegí el método de firma");
    expect(screen.getByRole("radio", { name: /Firma propia/ })).toBeChecked();
  });

  it("cumple las reglas de accesibilidad", async () => {
    const { container } = mount(batchFakes());
    await heading("Elegí el método de firma");
    expect((await axe(container)).violations).toEqual([]);
  });
});

describe("un certificado y un PIN para todo el lote", () => {
  it("prepara una vez, firma todos los hashes en una llamada y completa una vez", async () => {
    const fakes = batchFakes();
    fakes.server.selectProvider.mockResolvedValue(batchToContext(rawBatch()));
    fakes.server.complete.mockResolvedValue(
      batchToContext(
        rawBatch({ status: "completed", completed_at: "2026-10-08T10:32:07Z", documents: [0, 1, 2].map((i) => doc(i, { status: "signed", version_number: 2 })) }),
      ),
    );
    mount(fakes);
    await heading("Elegí el método de firma");
    await click("Firmar 3 documentos");
    await heading("Elegí el certificado");
    await click("Validar y continuar");
    await heading("Firma en lote completada");

    expect(fakes.server.prepare).toHaveBeenCalledTimes(1);
    expect(fakes.agent.sign).toHaveBeenCalledTimes(1);
    expect(fakes.agent.sign.mock.calls[0]![1]).toHaveLength(3); // los 3 desafíos, un solo PIN
    expect(fakes.server.complete).toHaveBeenCalledTimes(1);
    expect(fakes.server.complete.mock.calls[0]![0]).toHaveLength(3);
    expect(screen.getAllByText("3 de 3 documentos firmados").length).toBeGreaterThan(0);
    expect(fakes.host.batchCompleted).toHaveBeenCalledOnce();
    expect(fakes.host.signed).not.toHaveBeenCalled();
  });

  it("el certificado rechazado no pide el PIN", async () => {
    const fakes = batchFakes();
    fakes.server.selectProvider.mockResolvedValue(batchToContext(rawBatch()));
    fakes.server.prepare.mockRejectedValue(new ServerError("certificate_revoked", 422, "x"));
    mount(fakes);
    await heading("Elegí el método de firma");
    await click("Firmar 3 documentos");
    await heading("Elegí el certificado");
    await click("Validar y continuar");
    await heading("El certificado no pudo validarse");
    expect(fakes.agent.sign).not.toHaveBeenCalled();
  });

  it("con la firma de demostración completa el lote sin tocar al agente", async () => {
    const fakes = batchFakes(rawBatch({ provider: "local", allowed_providers: ["local"] }));
    const local = rawBatch({ provider: "local", allowed_providers: ["local"] });
    fakes.server.selectProvider.mockResolvedValue(batchToContext(local));
    fakes.server.complete.mockResolvedValue(
      batchToContext({ ...local, status: "completed", documents: [0, 1, 2].map((i) => doc(i, { status: "signed", version_number: 2 })) }),
    );
    mount(fakes);
    await heading("Elegí el método de firma");
    await click("Firmar 3 documentos");
    await heading("Firmar el documento");
    await click("Firmar");
    await heading("Firma en lote completada");
    expect(fakes.agent.sign).not.toHaveBeenCalled();
  });
});

describe("resultado parcial, descarga y reintento", () => {
  const partial = () =>
    batchToContext(
      rawBatch({
        status: "partial_failure",
        completed_at: "2026-10-08T10:32:07Z",
        documents: [
          doc(0, { status: "signed", version_number: 2 }),
          doc(1, { status: "failed", error: { code: null, detail: "Traceback secreto", http_status: 422 } }),
          doc(2, { status: "signed", version_number: 2 }),
        ],
      }),
    );

  it("muestra «2 de 3», el estado de cada uno y el motivo sin texto crudo", async () => {
    mount(makeFakes(partial()));
    await heading("Firma en lote finalizada");
    expect(screen.getAllByText("2 de 3 documentos firmados").length).toBeGreaterThan(0);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Firmado · v2");
    expect(items[1]).toHaveTextContent("Error:");
    expect(items[1]).toHaveTextContent("(422)");
    expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Descargar firmados (2)" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reintentar (1)" })).toBeEnabled();
  });

  it("descarga los firmados con el cliente", async () => {
    const fakes = makeFakes(partial());
    fakes.server.downloadPdf.mockResolvedValue({ blob: new Blob(["zip"]), filename: "documentos-firmados.zip" });
    mount(fakes);
    await heading("Firma en lote finalizada");
    await click("Descargar firmados (2)");
    await vi.waitFor(() => expect(fakes.saveFile).toHaveBeenCalledWith(expect.any(Blob), "documentos-firmados.zip"));
  });

  it("reintentar crea otro lote y abre su enlace", async () => {
    const fakes = makeFakes(partial());
    fakes.server.retry = vi.fn().mockResolvedValue({ id: "nuevo", signing_url: "http://x/sign/batch/nuevo#t=tok" });
    const navigate = vi.fn();
    fakes.services.navigate = navigate;
    mount(fakes);
    await heading("Firma en lote finalizada");
    await click("Reintentar (1)");
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith("http://x/sign/batch/nuevo#t=tok"));
  });

  it("si el reintento falla lo informa y permite reintentar", async () => {
    const fakes = makeFakes(partial());
    fakes.server.retry = vi.fn().mockRejectedValue(new ServerError("http_409", 409, "x"));
    mount(fakes);
    await heading("Firma en lote finalizada");
    await click("Reintentar (1)");
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo preparar el reintento");
    expect(screen.getByRole("button", { name: "Reintentar (1)" })).toBeEnabled();
  });

  it("sin firmados no ofrece descargar", async () => {
    const failed = batchToContext(
      rawBatch({ status: "failed", documents: [doc(0, { status: "failed", error: { code: null, detail: "x", http_status: 422 } })] }),
    );
    mount(makeFakes(failed));
    await heading("Firma en lote finalizada");
    expect(screen.queryByRole("button", { name: /Descargar firmados/ })).not.toBeInTheDocument();
    expect(screen.getAllByText("0 de 1 documentos firmados").length).toBeGreaterThan(0);
  });

  it("cumple las reglas de accesibilidad", async () => {
    const { container } = mount(makeFakes(partial()));
    await heading("Firma en lote finalizada");
    expect((await axe(container)).violations).toEqual([]);
  });
});

describe("mensaje al anfitrión", () => {
  it("informa el resultado del lote sin PDF, firmas ni token", () => {
    const post = vi.fn();
    const host = createHostNotifier(["https://gestor.example.org"], BATCH_ID, { postMessage: post });
    host.batchCompleted(
      {
        status: "partial_failure",
        documents: [doc(0, { status: "signed", version_number: 2 }), doc(1, { status: "failed", error: { code: "x", detail: "secreto", http_status: 422 } })],
      },
      BATCH_ID,
    );
    const [message, origin] = post.mock.calls[0]!;
    expect(origin).toBe("https://gestor.example.org");
    expect(message).toMatchObject({ source: "firmadoc", type: "firmadoc:batch-completed", batchId: BATCH_ID, status: "partial_failure", signed: 1, total: 2 });
    expect(message.documents).toEqual([
      { document_id: "doc-0", status: "signed", version_number: 2 },
      { document_id: "doc-1", status: "failed", version_number: null },
    ]);
    expect(JSON.stringify(message)).not.toMatch(/secreto|signature|base64|token/i);
  });
});

void makeCert;
