import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { describe, expect, it, vi } from "vitest";

import { App } from "../src/App";
import { AgentUnreachableError, ServerError } from "../src/api/errors";
import { createServerClient } from "../src/api/serverClient";
import { makeContext, makeFakes, signedContext, REQUEST_ID, TOKEN, jsonResponse, type Fakes } from "./fixtures";

const NOW = new Date("2026-10-08T12:00:00Z");

function mount(fakes: Fakes) {
  return render(<App services={fakes.services} now={() => NOW} />);
}
const heading = (name: string | RegExp) => screen.findByRole("heading", { name, level: 1 });
const click = (name: string | RegExp) => userEvent.click(screen.getByRole("button", { name }));

describe("elección del método", () => {
  const two = () => makeContext({ provider: "token", allowed_providers: ["token", "local"] });

  it("con varios métodos no consulta al agente hasta elegir el token", async () => {
    const fakes = makeFakes(two());
    fakes.server.selectProvider.mockResolvedValue(two());
    const createAgent = vi.fn(fakes.services.createAgent);
    fakes.services.createAgent = createAgent;
    mount(fakes);
    await heading("¿Cómo querés firmar?");
    expect(createAgent).not.toHaveBeenCalled();
    expect(fakes.agent.certificates).not.toHaveBeenCalled();

    await click(/Firmar con mi token/);
    await heading("Elegí el certificado");
    expect(fakes.server.selectProvider).toHaveBeenCalledWith("token");
    expect(createAgent).toHaveBeenCalledOnce();
  });

  it("elegir la firma de demostración la completa sin tocar al agente", async () => {
    const fakes = makeFakes(two());
    fakes.server.selectProvider.mockResolvedValue({ ...two(), provider: "local" });
    mount(fakes);
    await heading("¿Cómo querés firmar?");
    await click(/Firma electrónica de demostración/);
    await heading("Firmar el documento");
    await click("Firmar");
    await heading("Documento firmado correctamente");
    expect(fakes.agent.certificates).not.toHaveBeenCalled();
  });

  it("si el agente no está, se puede elegir otro método", async () => {
    const fakes = makeFakes(two());
    fakes.agent.certificates.mockRejectedValue(new AgentUnreachableError());
    fakes.server.selectProvider.mockResolvedValue(two());
    mount(fakes);
    await heading("¿Cómo querés firmar?");
    await click(/Firmar con mi token/);
    await heading("No detectamos Firmadoc Agent");
    await click("Elegir otro método");
    await heading("¿Cómo querés firmar?");
  });

  it("un rechazo del servidor se informa y permite reintentar", async () => {
    const fakes = makeFakes(two());
    fakes.server.selectProvider.mockRejectedValue(new ServerError("provider_not_allowed", 422, "x"));
    mount(fakes);
    await heading("¿Cómo querés firmar?");
    await click(/Firmar con mi token/);
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo elegir ese método");
    expect(screen.getByRole("button", { name: /Firmar con mi token/ })).toBeEnabled();
  });

  it("con un solo método no hay elección ni 'Elegir otro método'", async () => {
    const fakes = makeFakes(makeContext({ provider: "local", allowed_providers: ["local"] }));
    mount(fakes);
    await heading("Firmar el documento");
    expect(screen.queryByRole("button", { name: "Elegir otro método" })).not.toBeInTheDocument();
  });

  it("cumple las reglas de accesibilidad", async () => {
    const { container } = mount(makeFakes(two()));
    await heading("¿Cómo querés firmar?");
    expect((await axe(container)).violations).toEqual([]);
  });
});

describe("firma remota", () => {
  const remote = () => makeContext({ provider: "firmar", allowed_providers: ["firmar"] });
  const prepared = {
    challenges: [],
    expires_at: "2099-01-01T00:00:00Z",
    remote: { operation_id: "op-1", authorization_url: "https://servicio.example/firmar/op-1" },
  };

  it("envía el documento, muestra el enlace seguro y termina cuando el servicio firma", async () => {
    const fakes = makeFakes(remote());
    fakes.server.prepare.mockResolvedValue(prepared);
    fakes.services.pollMs = 10;
    mount(fakes);
    await heading("Firmar con el servicio de firma remota");
    await click("Continuar");
    await heading("Esperando la firma en el servicio remoto");
    const link = screen.getByRole("link", { name: "Continuar en el servicio de firma" });
    expect(link).toHaveAttribute("href", "https://servicio.example/firmar/op-1");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");

    fakes.server.getContext.mockResolvedValue(signedContext({ provider: "firmar" }));
    await heading("Documento firmado correctamente");
    expect(fakes.host.signed).toHaveBeenCalledOnce();
  });

  it("si el servicio rechaza, informa y avisa al anfitrión", async () => {
    const fakes = makeFakes(remote());
    fakes.server.prepare.mockResolvedValue(prepared);
    fakes.services.pollMs = 10;
    mount(fakes);
    await heading("Firmar con el servicio de firma remota");
    await click("Continuar");
    await heading("Esperando la firma en el servicio remoto");
    fakes.server.getContext.mockResolvedValue({ ...remote(), status: "failed" });
    await heading("La firma no se completó");
    expect(fakes.host.failed).toHaveBeenCalledWith("request_failed");
  });

  it("servicio no disponible: se puede reintentar", async () => {
    const fakes = makeFakes(remote());
    fakes.server.prepare
      .mockRejectedValueOnce(new ServerError("remote_unavailable", 503, "x"))
      .mockResolvedValue(prepared);
    mount(fakes);
    await heading("Firmar con el servicio de firma remota");
    await click("Continuar");
    expect(await screen.findByRole("alert")).toHaveTextContent("no está disponible");
    await click("Reintentar");
    await heading("Esperando la firma en el servicio remoto");
  });

  it("recarga con la firma en curso: espera sin enlace y deja de consultar al cancelar", async () => {
    const fakes = makeFakes({ ...remote(), status: "signing" });
    fakes.services.pollMs = 10;
    mount(fakes);
    await heading("Esperando la firma en el servicio remoto");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    await click("Cancelar");
    await heading("Firma cancelada");
    const calls = fakes.server.getContext.mock.calls.length;
    await new Promise((r) => setTimeout(r, 80));
    expect(fakes.server.getContext.mock.calls.length).toBe(calls);
  });

  it("nunca enlaza una URL que no sea http(s)", async () => {
    const fakes = makeFakes(remote());
    fakes.server.prepare.mockResolvedValue({
      ...prepared,
      remote: { operation_id: "x", authorization_url: "javascript:alert(1)" },
    });
    mount(fakes);
    await heading("Firmar con el servicio de firma remota");
    await click("Continuar");
    await heading("Esperando la firma en el servicio remoto");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});

describe("serverClient: elegir método", () => {
  const client = (fetchFn: unknown) =>
    createServerClient({ requestId: REQUEST_ID, token: TOKEN, sessionRef: "s", fetchFn: fetchFn as typeof fetch });

  it("envía el método elegido y valida el contexto devuelto", async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(makeContext({ provider: "local", allowed_providers: ["token", "local"] })));
    const context = await client(fetchFn).selectProvider("local");
    expect(context.provider).toBe("local");
    const [url, init] = fetchFn.mock.calls[0]!;
    expect(url).toBe(`/api/v1/widget/requests/${REQUEST_ID}/provider`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ provider: "local" });
  });

  it("rechaza un contexto sin los métodos disponibles", async () => {
    const bad: Record<string, unknown> = { ...makeContext() };
    delete bad.allowed_providers;
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(bad));
    await expect(client(fetchFn).selectProvider("local")).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("prepare acepta la operación remota y rechaza una malformada", async () => {
    const ok = vi.fn().mockResolvedValue(jsonResponse({ challenges: [], expires_at: "x", remote: { operation_id: "1", authorization_url: "https://s/1" } }));
    expect((await client(ok).prepare()).remote?.operation_id).toBe("1");
    const bad = vi.fn().mockResolvedValue(jsonResponse({ challenges: [], expires_at: "x", remote: { operation_id: 1 } }));
    await expect(client(bad).prepare()).rejects.toMatchObject({ code: "invalid_response" });
  });
});
