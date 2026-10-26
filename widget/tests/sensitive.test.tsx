/** Ni el token ni las firmas ni el PIN quedan en el navegador, en la consola ni en las URL. */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App";
import { createAgentClient } from "../src/api/agentClient";
import { createServerClient } from "../src/api/serverClient";
import { createHostNotifier } from "../src/embed/hostMessages";
import { challenge, jsonResponse, makeCert, makeContext, REQUEST_ID, signedContext, TOKEN } from "./fixtures";

const SIGNATURE = "U0lHTkFUVVJBLVNFQ1JFVEE=";
const AGENT = "http://127.0.0.1:47123";

interface Call {
  url: string;
  headers: Record<string, string>;
  body: string | undefined;
}

function installFetch(provider: "token" | "local") {
  const calls: Call[] = [];
  const fetchFn = vi.fn(async (url: string, init: RequestInit = {}) => {
    calls.push({ url, headers: (init.headers ?? {}) as Record<string, string>, body: init.body as string | undefined });
    if (url.startsWith(AGENT)) {
      if (url.endsWith("/certificates")) return jsonResponse({ agent_version: "0.1.0", certificates: [makeCert()] });
      return jsonResponse({ signatures: [{ challenge_id: challenge.challenge_id, signature_base64: SIGNATURE }] });
    }
    if (url.endsWith("/prepare")) {
      return jsonResponse({ challenges: [challenge], expires_at: "2099-01-01T00:00:00Z" });
    }
    if (url.endsWith("/complete")) return jsonResponse(signedContext({ provider }));
    return jsonResponse(makeContext({ provider }));
  });
  return { fetchFn: fetchFn as unknown as typeof fetch, calls };
}

const consoleMethods = ["log", "info", "warn", "error", "debug"] as const;

describe("datos sensibles", () => {
  const spies: ReturnType<typeof vi.spyOn>[] = [];

  beforeEach(() => {
    for (const method of consoleMethods) spies.push(vi.spyOn(console, method).mockImplementation(() => {}));
  });

  afterEach(() => {
    spies.splice(0).forEach((s) => s.mockRestore());
    localStorage.clear();
    sessionStorage.clear();
  });

  async function runFlow(provider: "token" | "local") {
    const { fetchFn, calls } = installFetch(provider);
    const services = {
      server: createServerClient({ requestId: REQUEST_ID, token: TOKEN, sessionRef: "sesion", fetchFn }),
      createAgent: (url: string) => createAgentClient({ baseUrl: url, fetchFn }),
      createHost: (origins: string[], id: string) => createHostNotifier(origins, id, { postMessage: vi.fn() }),
      saveFile: vi.fn(),
    };
    render(<App services={services} />);
    if (provider === "token") {
      await userEvent.click(await screen.findByRole("button", { name: "Validar y continuar" }));
    } else {
      await userEvent.click(await screen.findByRole("button", { name: "Firmar" }));
    }
    await screen.findByRole("heading", { name: "Documento firmado correctamente" });
    return calls;
  }

  it.each(["token", "local"] as const)("flujo %s: nada sensible en almacenamiento, cookies ni consola", async (provider) => {
    await runFlow(provider);

    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
    for (const spy of spies) {
      const logged = JSON.stringify(spy.mock.calls);
      expect(logged).not.toContain(TOKEN);
      expect(logged).not.toContain(SIGNATURE);
    }
    expect(window.location.href).not.toContain(TOKEN);
  });

  it("el token solo viaja en la cabecera Authorization hacia el servidor de Firmadoc", async () => {
    const calls = await runFlow("token");
    for (const call of calls) {
      expect(call.url).not.toContain(TOKEN); // jamás en una URL
      if (call.url.startsWith(AGENT)) {
        // el agente nunca recibe el token ni la sesión del servidor
        expect(JSON.stringify(call.headers)).not.toContain(TOKEN);
        expect(call.headers["Authorization"]).toBeUndefined();
        expect(call.body ?? "").not.toContain(TOKEN);
      } else {
        expect(call.headers["Authorization"]).toBe(`Bearer ${TOKEN}`);
      }
    }
  });

  it("las firmas solo se envían al servidor de Firmadoc, nunca a otro destino", async () => {
    const calls = await runFlow("token");
    const withSignature = calls.filter((c) => (c.body ?? "").includes(SIGNATURE));
    expect(withSignature).toHaveLength(1);
    expect(withSignature[0]!.url).toMatch(/\/complete$/);
  });

  it("el widget no tiene ningún campo de PIN", async () => {
    await runFlow("token"); // recorre toda la interfaz del flujo token
    expect(document.querySelector('input[type="password"]')).toBeNull();
    expect(screen.queryByLabelText(/pin/i)).toBeNull();
  });
});
