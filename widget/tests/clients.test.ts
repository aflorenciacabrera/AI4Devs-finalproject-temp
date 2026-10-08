import { describe, expect, it, vi } from "vitest";

import { createAgentClient } from "../src/api/agentClient";
import { AgentError, AgentUnreachableError, ServerError } from "../src/api/errors";
import { createServerClient } from "../src/api/serverClient";
import { challenge, jsonResponse, makeCert, makeContext, REQUEST_ID, signedContext, TOKEN } from "./fixtures";

function server(fetchFn: typeof fetch, timeoutMs?: number) {
  return createServerClient({
    requestId: REQUEST_ID,
    token: TOKEN,
    sessionRef: "sesion-1",
    fetchFn,
    timeoutMs,
  });
}

const agent = (fetchFn: typeof fetch, extra: object = {}) =>
  createAgentClient({ baseUrl: "http://127.0.0.1:47123/", fetchFn, ...extra });

describe("serverClient", () => {
  it("pide el contexto con el token en la cabecera y nunca en la URL", async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(makeContext()));
    const context = await server(fetchFn as unknown as typeof fetch).getContext();
    expect(context.document_name).toBe("resolucion-0142-2026.pdf");
    const [url, init] = fetchFn.mock.calls[0]!;
    expect(url).toBe(`/api/v1/widget/requests/${REQUEST_ID}`);
    expect(url).not.toContain(TOKEN);
    expect(init.headers.Authorization).toBe(`Bearer ${TOKEN}`);
    expect(init.headers["X-Session-Ref"]).toBe("sesion-1");
    expect(init.credentials).toBe("omit");
    expect(init.cache).toBe("no-store");
  });

  it("prepare envía el certificado; con local, un cuerpo vacío", async () => {
    const fetchFn = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(jsonResponse({ challenges: [challenge], expires_at: "2099-01-01T00:00:00Z" })),
      );
    const client = server(fetchFn as unknown as typeof fetch);
    await client.prepare("PEM");
    await client.prepare();
    expect(JSON.parse(fetchFn.mock.calls[0]![1].body)).toEqual({ certificate_pem: "PEM" });
    expect(JSON.parse(fetchFn.mock.calls[1]![1].body)).toEqual({});
  });

  it("complete envía las firmas y devuelve el contexto", async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(signedContext()));
    const result = await server(fetchFn as unknown as typeof fetch).complete([
      { challenge_id: "c1", signature_base64: "AAA" },
    ]);
    expect(result.status).toBe("signed");
    expect(JSON.parse(fetchFn.mock.calls[0]![1].body)).toEqual({
      signatures: [{ challenge_id: "c1", signature_base64: "AAA" }],
    });
  });

  it.each([
    [401, { detail: "no", code: "invalid_token" }, "invalid_token"],
    [403, { detail: "otro CUIL", code: "cuil_mismatch" }, "cuil_mismatch"],
    [422, { detail: "revocado", code: "certificate_revoked" }, "certificate_revoked"],
    [409, { detail: "venció" }, "http_409"],
    [500, "no es json", "http_500"],
  ])("normaliza el error HTTP %s", async (status, body, code) => {
    const fetchFn = vi.fn().mockResolvedValue(
      typeof body === "string" ? new Response(body, { status }) : jsonResponse(body, status),
    );
    await expect(server(fetchFn as unknown as typeof fetch).prepare("PEM")).rejects.toMatchObject({
      name: "ServerError",
      status,
      code,
    });
  });

  it("red caída", async () => {
    const fetchFn = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(server(fetchFn as unknown as typeof fetch).getContext()).rejects.toMatchObject({
      code: "network_error",
      status: 0,
    });
  });

  it("tiempo agotado", async () => {
    const fetchFn = vi.fn(
      (_url: string, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal!.addEventListener("abort", () => reject(new DOMException("abort", "AbortError")));
        }),
    );
    await expect(server(fetchFn as unknown as typeof fetch, 20).getContext()).rejects.toMatchObject({
      code: "network_error",
    });
  });

  it.each([
    ["contexto sin forma", () => jsonResponse({ hola: 1 })],
    ["texto plano", () => new Response("hola", { status: 200 })],
  ])("respuesta mal formada: %s", async (_name, make) => {
    const fetchFn = vi.fn().mockResolvedValue(make());
    await expect(server(fetchFn as unknown as typeof fetch).getContext()).rejects.toMatchObject({
      code: "invalid_response",
    });
  });

  it("prepare rechaza desafíos mal formados", async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ challenges: [{ nada: 1 }] }));
    await expect(server(fetchFn as unknown as typeof fetch).prepare("PEM")).rejects.toBeInstanceOf(
      ServerError,
    );
  });

  it("descarga el PDF como Blob y toma el nombre de la cabecera", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response("%PDF-1.7", {
        status: 200,
        headers: { "Content-Disposition": 'attachment; filename="documento-firmado-v2.pdf"' },
      }),
    );
    const { blob, filename } = await server(fetchFn as unknown as typeof fetch).downloadPdf();
    expect(filename).toBe("documento-firmado-v2.pdf");
    expect(await blob.text()).toBe("%PDF-1.7");
    expect(fetchFn.mock.calls[0]![0]).not.toContain(TOKEN);
  });
});

describe("agentClient", () => {
  it("lista los certificados con CORS sin credenciales", async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ agent_version: "0.1.0", certificates: [makeCert()] }));
    const certs = await agent(fetchFn as unknown as typeof fetch).certificates();
    expect(certs).toHaveLength(1);
    const [url, init] = fetchFn.mock.calls[0]!;
    expect(url).toBe("http://127.0.0.1:47123/certificates");
    expect(init).toMatchObject({ mode: "cors", credentials: "omit", cache: "no-store", method: "GET" });
  });

  it("firma enviando solo lo que el contrato pide", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      jsonResponse({ signatures: [{ challenge_id: "c9e1a7b4", signature_base64: "AAA=" }] }),
    );
    const signatures = await agent(fetchFn as unknown as typeof fetch).sign("SERIE1:01", [challenge]);
    expect(signatures[0]!.signature_base64).toBe("AAA=");
    const [url, init] = fetchFn.mock.calls[0]!;
    expect(url).toBe("http://127.0.0.1:47123/sign");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({
      certificate_id: "SERIE1:01",
      items: [
        {
          challenge_id: challenge.challenge_id,
          document_name: challenge.document_name,
          hash_algorithm: "SHA-256",
          hash_to_sign: challenge.hash_to_sign,
        },
      ],
    });
  });

  it("distingue agente ausente de error del agente", async () => {
    const down = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(agent(down as unknown as typeof fetch).certificates()).rejects.toBeInstanceOf(
      AgentUnreachableError,
    );

    const refused = vi.fn().mockResolvedValue(jsonResponse({ code: "origin_not_allowed", detail: "no" }, 403));
    const error = await agent(refused as unknown as typeof fetch).certificates().catch((e) => e);
    expect(error).toBeInstanceOf(AgentError);
    expect(error).toMatchObject({ code: "origin_not_allowed", status: 403 });
  });

  it.each([
    ["token_not_found", 404],
    ["pkcs11_unavailable", 500],
    ["user_cancelled", 409],
    ["pin_incorrect", 401],
    ["pin_locked", 423],
    ["busy", 429],
  ])("propaga el código %s", async (code, status) => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ code, detail: "x" }, status));
    await expect(agent(fetchFn as unknown as typeof fetch).sign("id", [challenge])).rejects.toMatchObject({
      code,
      status,
    });
  });

  it("detección con tiempo límite corto: sin respuesta equivale a agente ausente", async () => {
    const hang = vi.fn(
      (_url: string, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal!.addEventListener("abort", () => reject(new DOMException("abort", "AbortError")));
        }),
    );
    await expect(
      agent(hang as unknown as typeof fetch, { detectTimeoutMs: 20 }).certificates(),
    ).rejects.toBeInstanceOf(AgentUnreachableError);
  });

  it("respuestas mal formadas", async () => {
    const bad = vi.fn().mockResolvedValue(jsonResponse({ certificates: [{ id: 1 }] }));
    await expect(agent(bad as unknown as typeof fetch).certificates()).rejects.toMatchObject({
      code: "invalid_response",
    });
    const badSign = vi.fn().mockResolvedValue(jsonResponse({ signatures: [{ nada: true }] }));
    await expect(agent(badSign as unknown as typeof fetch).sign("id", [challenge])).rejects.toMatchObject({
      code: "invalid_response",
    });
  });
});
