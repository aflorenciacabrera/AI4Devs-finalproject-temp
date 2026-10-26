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
  const TITLE = "Elegí el método de firma";
  const pick = (name: RegExp) => userEvent.click(screen.getByRole("radio", { name }));

  it("consulta al agente para mostrar su estado y firma con el token preseleccionado", async () => {
    const fakes = makeFakes(two());
    fakes.server.selectProvider.mockResolvedValue(two());
    const createAgent = vi.fn(fakes.services.createAgent);
    fakes.services.createAgent = createAgent;
    mount(fakes);
    await heading(TITLE);
    expect(await screen.findByText("Firmadoc Agent conectado · token detectado")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Firma con token/ })).toBeChecked();

    await click("Firmar");
    await heading("Elegí el certificado");
    expect(fakes.server.selectProvider).toHaveBeenCalledWith("token");
  });

  it("cada método lleva su etiqueta de validez", async () => {
    mount(makeFakes(two()));
    await heading(TITLE);
    expect(screen.getByText("Firma digital")).toBeInTheDocument();
    expect(screen.getByText("Demostración")).toBeInTheDocument();
    expect(screen.getByText(/no tiene la presunción legal/)).toBeInTheDocument();
  });

  it("muestra la tarjeta del documento con su estado y vencimiento", async () => {
    const fakes = makeFakes({
      ...two(),
      page_count: 3,
      size_bytes: 493568,
      signing_status: "pending_signature",
      signature_deadline: "2026-09-15T12:00:00-03:00",
    });
    mount(fakes);
    await heading(TITLE);
    expect(screen.getByText("resolucion-0142-2026.pdf")).toBeInTheDocument();
    expect(screen.getByText("3 páginas · 482 KB")).toBeInTheDocument();
    expect(screen.getByText("Pendiente de firma")).toBeInTheDocument();
    expect(screen.getByText(/Vence 15\/09\/2026/)).toBeInTheDocument();
  });

  it("elegir la firma de demostración la completa sin tocar al agente para firmar", async () => {
    const fakes = makeFakes(two());
    fakes.server.selectProvider.mockResolvedValue({ ...two(), provider: "local" });
    mount(fakes);
    await heading(TITLE);
    await pick(/Firma propia/);
    await click("Firmar");
    await heading("Firmar el documento");
    await click("Firmar");
    await heading("Documento firmado correctamente");
    expect(fakes.server.selectProvider).toHaveBeenCalledWith("local");
    expect(fakes.agent.sign).not.toHaveBeenCalled();
  });

  it("si el agente no está, lo indica y se puede elegir otro método", async () => {
    const fakes = makeFakes(two());
    fakes.agent.certificates.mockRejectedValue(new AgentUnreachableError());
    fakes.server.selectProvider.mockResolvedValue(two());
    mount(fakes);
    await heading(TITLE);
    expect(await screen.findByText("No detectamos Firmadoc Agent en esta PC")).toBeInTheDocument();
    await pick(/Firma con token/);
    await click("Firmar");
    await heading("No detectamos Firmadoc Agent");
    await click("Elegir otro método");
    await heading(TITLE);
  });

  it("un rechazo del servidor se informa y permite reintentar", async () => {
    const fakes = makeFakes(two());
    fakes.server.selectProvider.mockRejectedValue(new ServerError("provider_not_allowed", 422, "x"));
    mount(fakes);
    await heading(TITLE);
    await click("Firmar");
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo elegir ese método");
    expect(screen.getByRole("button", { name: "Firmar" })).toBeEnabled();
  });

  it("se elige con el teclado", async () => {
    const fakes = makeFakes(two());
    fakes.server.selectProvider.mockResolvedValue({ ...two(), provider: "local" });
    mount(fakes);
    await heading(TITLE);
    screen.getByRole("radio", { name: /Firma con token/ }).focus();
    await userEvent.keyboard("{ArrowDown}");
    expect(screen.getByRole("radio", { name: /Firma propia/ })).toBeChecked();
  });

  it("con un solo método no hay elección ni 'Elegir otro método'", async () => {
    const fakes = makeFakes(makeContext({ provider: "local", allowed_providers: ["local"] }));
    mount(fakes);
    await heading("Firmar el documento");
    expect(screen.queryByRole("button", { name: "Elegir otro método" })).not.toBeInTheDocument();
  });

  it("cumple las reglas de accesibilidad", async () => {
    const { container } = mount(makeFakes(two()));
    await heading(TITLE);
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
    expect(link).toHaveAttribute("rel", "noreferrer");

    // el clic abre el servicio en una ventana emergente chica (no en otra pestaña)…
    const service = { closed: false, close: vi.fn(function (this: { closed: boolean }) { this.closed = true; }) };
    const open = vi.spyOn(window, "open").mockReturnValue(service as unknown as Window);
    try {
      const event = new MouseEvent("click", { bubbles: true, cancelable: true });
      link.dispatchEvent(event);
      expect(open).toHaveBeenCalledTimes(1);
      expect(open.mock.calls[0]![0]).toBe("https://servicio.example/firmar/op-1");
      expect(open.mock.calls[0]![1]).toBe("firmadoc-servicio-remoto");
      expect(String(open.mock.calls[0]![2])).toContain("popup=yes");
      expect(event.defaultPrevented).toBe(true); // la pestaña no se abre además de la ventana

      // …y se cierra sola cuando el servicio firma
      fakes.server.getContext.mockResolvedValue(signedContext({ provider: "firmar" }));
      await heading("Documento firmado correctamente");
      expect(service.close).toHaveBeenCalledTimes(1);
      expect(fakes.host.signed).toHaveBeenCalledOnce();
    } finally {
      open.mockRestore();
    }
  });

  it("si el navegador bloquea la ventana emergente, el enlace abre una pestaña", async () => {
    const fakes = makeFakes(remote());
    fakes.server.prepare.mockResolvedValue(prepared);
    mount(fakes);
    await heading("Firmar con el servicio de firma remota");
    await click("Continuar");
    await heading("Esperando la firma en el servicio remoto");
    const open = vi.spyOn(window, "open").mockReturnValue(null);
    try {
      const event = new MouseEvent("click", { bubbles: true, cancelable: true });
      screen.getByRole("link", { name: "Continuar en el servicio de firma" }).dispatchEvent(event);
      expect(open).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(false); // sigue el enlace: target=_blank
    } finally {
      open.mockRestore();
    }
  });

  it("cancelar la espera cierra la ventana del servicio", async () => {
    const fakes = makeFakes(remote());
    fakes.server.prepare.mockResolvedValue(prepared);
    mount(fakes);
    await heading("Firmar con el servicio de firma remota");
    await click("Continuar");
    await heading("Esperando la firma en el servicio remoto");
    const service = { closed: false, close: vi.fn() };
    const open = vi.spyOn(window, "open").mockReturnValue(service as unknown as Window);
    try {
      screen.getByRole("link", { name: "Continuar en el servicio de firma" }).dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      await click("Cancelar");
      expect(service.close).toHaveBeenCalledTimes(1);
    } finally {
      open.mockRestore();
    }
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
