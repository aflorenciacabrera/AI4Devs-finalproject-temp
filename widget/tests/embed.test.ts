import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { createHostNotifier } from "../src/embed/hostMessages";
import "../src/embed/widgetElement"; // registra <firmadoc-widget>
import type { FirmadocWidgetElement } from "../src/embed/widgetElement";
import { signedContext } from "./fixtures";

const REQUEST = "11111111-2222-4333-8444-555555555555";

describe("mensajes hacia la página anfitriona", () => {
  it("envía a cada origen permitido, nunca a '*'", () => {
    const parent = { postMessage: vi.fn() };
    const host = createHostNotifier(["https://a.example.org", "https://b.example.org"], REQUEST, parent);
    host.ready();
    expect(parent.postMessage).toHaveBeenCalledTimes(2);
    const origins = parent.postMessage.mock.calls.map((c) => c[1]);
    expect(origins).toEqual(["https://a.example.org", "https://b.example.org"]);
    expect(origins).not.toContain("*");
    expect(parent.postMessage.mock.calls[0]![0]).toEqual({
      source: "firmadoc",
      type: "firmadoc:ready",
      requestId: REQUEST,
    });
  });

  it("ignora un '*' o un origen vacío aunque venga en la lista", () => {
    const parent = { postMessage: vi.fn() };
    createHostNotifier(["*", "", "https://a.example.org"], REQUEST, parent).ready();
    expect(parent.postMessage.mock.calls.map((c) => c[1])).toEqual(["https://a.example.org"]);
  });

  it("sin origenes permitidos no entrega nada", () => {
    const parent = { postMessage: vi.fn() };
    const host = createHostNotifier([], REQUEST, parent);
    host.ready();
    host.signed(null);
    expect(parent.postMessage).not.toHaveBeenCalled();
  });

  it("sin página anfitriona (ventana propia) no falla", () => {
    expect(() => createHostNotifier(["https://a.example.org"], REQUEST, null).ready()).not.toThrow();
  });

  it("firmado: solo los datos del documento, sin el PDF ni la URL de descarga ni el token", () => {
    const parent = { postMessage: vi.fn() };
    const document = {
      ...signedContext().document!,
      signed_document_base64: "JVBERi0xLjQK",
    };
    createHostNotifier(["https://a.example.org"], REQUEST, parent).signed(document);
    const message = parent.postMessage.mock.calls[0]![0];
    expect(message.type).toBe("firmadoc:signed");
    expect(message.document).toEqual({
      id: "doc-1",
      version_number: 2,
      is_active_version: true,
      signing_status: "signed",
      signature_level: "B-B",
    });
    const text = JSON.stringify(message);
    expect(text).not.toContain("JVBERi0x");
    expect(text).not.toContain("download");
    expect(text.toLowerCase()).not.toContain("token");
  });

  it("falla: solo el código, sin detalles internos", () => {
    const parent = { postMessage: vi.fn() };
    createHostNotifier(["https://a.example.org"], REQUEST, parent).failed("http_422");
    expect(parent.postMessage.mock.calls[0]![0]).toEqual({
      source: "firmadoc",
      type: "firmadoc:failed",
      requestId: REQUEST,
      code: "http_422",
    });
  });

  it("cancelado y cerrado", () => {
    const parent = { postMessage: vi.fn() };
    const host = createHostNotifier(["https://a.example.org"], REQUEST, parent);
    host.cancelled();
    host.closed();
    expect(parent.postMessage.mock.calls.map((c) => c[0].type)).toEqual([
      "firmadoc:cancelled",
      "firmadoc:closed",
    ]);
  });
});

describe("el widget no escucha mensajes entrantes", () => {
  function sources(dir: string): string[] {
    return readdirSync(dir).flatMap((name) => {
      const path = join(dir, name);
      return statSync(path).isDirectory() ? sources(path) : /\.(ts|tsx)$/.test(name) ? [path] : [];
    });
  }

  it("ningún módulo de la aplicación registra un listener de 'message'", () => {
    const widgetSources = sources(resolve(__dirname, "../src")).filter(
      (file) => !file.endsWith("widgetElement.ts"), // ese es el lado de la página anfitriona
    );
    expect(widgetSources.length).toBeGreaterThan(10);
    for (const file of widgetSources) {
      const code = readFileSync(file, "utf-8");
      expect(code, file).not.toMatch(/addEventListener\(\s*["']message["']/);
      expect(code, file).not.toMatch(/\.onmessage\s*=/);
    }
  });
});

describe("<firmadoc-widget>", () => {
  const URL_OK = "https://firmadoc.example.org/sign/abc#t=token";

  afterEach(() => {
    document.body.innerHTML = "";
  });

  function mount(attrs: Record<string, string> = { "signing-url": URL_OK }) {
    const el = document.createElement("firmadoc-widget") as FirmadocWidgetElement;
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    document.body.appendChild(el);
    const iframe = el.shadowRoot!.querySelector("iframe") as HTMLIFrameElement | null;
    return { el, iframe };
  }

  function post(iframe: HTMLIFrameElement, data: unknown, origin = "https://firmadoc.example.org") {
    window.dispatchEvent(new MessageEvent("message", { data, origin, source: iframe.contentWindow }));
  }

  it("crea el iframe con la URL, el título y los permisos mínimos", () => {
    const { iframe } = mount();
    expect(iframe).not.toBeNull();
    expect(iframe!.src).toBe(URL_OK);
    expect(iframe!.title).toMatch(/Firmadoc/);
    expect(iframe!.getAttribute("sandbox")).toBe("allow-scripts allow-same-origin allow-downloads allow-popups allow-popups-to-escape-sandbox");
    expect(iframe!.getAttribute("allow")).toContain("local-network-access");
    expect(iframe!.referrerPolicy).toBe("no-referrer");
  });

  it("reemite los mensajes del widget como eventos DOM", () => {
    const { el, iframe } = mount();
    const signed = vi.fn();
    const closed = vi.fn();
    el.addEventListener("firmadoc-signed", signed);
    el.addEventListener("firmadoc-closed", closed);
    const message = { source: "firmadoc", type: "firmadoc:signed", requestId: "r", document: { id: "d" } };
    post(iframe!, message);
    post(iframe!, { source: "firmadoc", type: "firmadoc:closed", requestId: "r" });
    expect(signed).toHaveBeenCalledOnce();
    expect((signed.mock.calls[0]![0] as CustomEvent).detail).toEqual(message);
    expect(closed).toHaveBeenCalledOnce();
  });

  it("ignora mensajes de otro origen", () => {
    const { el, iframe } = mount();
    const any = vi.fn();
    el.addEventListener("firmadoc-signed", any);
    post(iframe!, { source: "firmadoc", type: "firmadoc:signed" }, "https://evil.example.org");
    expect(any).not.toHaveBeenCalled();
  });

  it("ignora mensajes de otra ventana", () => {
    const { el } = mount();
    const other = document.createElement("iframe");
    document.body.appendChild(other);
    const any = vi.fn();
    el.addEventListener("firmadoc-signed", any);
    post(other, { source: "firmadoc", type: "firmadoc:signed" });
    expect(any).not.toHaveBeenCalled();
  });

  it.each([
    ["sin source", { type: "firmadoc:signed" }],
    ["tipo desconocido", { source: "firmadoc", type: "firmadoc:otro" }],
    ["no es un objeto", "texto"],
    ["null", null],
  ])("ignora mensajes mal formados (%s)", (_name, data) => {
    const { el, iframe } = mount();
    const any = vi.fn();
    for (const name of ["firmadoc-signed", "firmadoc-ready", "firmadoc-failed"]) el.addEventListener(name, any);
    post(iframe!, data);
    expect(any).not.toHaveBeenCalled();
  });

  it("al cambiar signing-url recarga el mismo iframe con la nueva URL y su nuevo origen", () => {
    const { el, iframe } = mount();
    el.setAttribute("signing-url", "https://otro.example.org/sign/xyz#t=t2");
    const again = el.shadowRoot!.querySelectorAll("iframe");
    expect(again).toHaveLength(1);
    expect(again[0]).toBe(iframe);
    expect(iframe!.src).toBe("https://otro.example.org/sign/xyz#t=t2");

    const any = vi.fn();
    el.addEventListener("firmadoc-ready", any);
    post(iframe!, { source: "firmadoc", type: "firmadoc:ready" }, "https://firmadoc.example.org");
    expect(any).not.toHaveBeenCalled(); // el origen viejo ya no vale
    post(iframe!, { source: "firmadoc", type: "firmadoc:ready" }, "https://otro.example.org");
    expect(any).toHaveBeenCalledOnce();
  });

  it.each(["javascript:alert(1)", "data:text/html,hola", "ftp://x.example.org/a"])(
    "rechaza una signing-url peligrosa (%s) y avisa",
    (bad) => {
      const el = document.createElement("firmadoc-widget");
      const failed = vi.fn();
      el.addEventListener("firmadoc-failed", failed);
      el.setAttribute("signing-url", bad);
      document.body.appendChild(el);
      expect(el.shadowRoot!.querySelector("iframe")).toBeNull();
      expect((failed.mock.calls[0]![0] as CustomEvent).detail).toMatchObject({ code: "invalid_url" });
    },
  );

  it("sin signing-url no hay iframe", () => {
    expect(mount({}).iframe).toBeNull();
  });

  it("al quitarse del DOM deja de escuchar", () => {
    const { el, iframe } = mount();
    const any = vi.fn();
    el.addEventListener("firmadoc-signed", any);
    el.remove();
    post(iframe!, { source: "firmadoc", type: "firmadoc:signed" });
    expect(any).not.toHaveBeenCalled();
  });
});
