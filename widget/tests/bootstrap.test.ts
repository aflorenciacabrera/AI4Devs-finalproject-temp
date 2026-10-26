import { describe, expect, it, vi } from "vitest";

import { applyTheme, newSessionRef, requestIdFromPath, takeToken } from "../src/bootstrap/token";

const ID = "11111111-2222-4333-8444-555555555555";

function loc(hash: string, pathname = `/sign/${ID}`, search = "") {
  return { hash, pathname, search };
}

describe("takeToken", () => {
  it("lee el token del fragmento y lo borra de la barra de direcciones y del historial", () => {
    const history = { replaceState: vi.fn() };
    expect(takeToken(loc("#t=abc.def"), history)).toBe("abc.def");
    expect(history.replaceState).toHaveBeenCalledWith(null, "", `/sign/${ID}`);
  });

  it("conserva la query y descarta solo el fragmento", () => {
    const history = { replaceState: vi.fn() };
    takeToken(loc("#t=abc", `/sign/${ID}`, "?x=1"), history);
    expect(history.replaceState).toHaveBeenCalledWith(null, "", `/sign/${ID}?x=1`);
  });

  it("acepta otros parámetros en el fragmento", () => {
    expect(takeToken(loc("#foo=1&t=tok&bar=2"), { replaceState: vi.fn() })).toBe("tok");
  });

  it("decodifica el token", () => {
    expect(takeToken(loc("#t=a%2Bb"), { replaceState: vi.fn() })).toBe("a+b");
  });

  it.each(["", "#", "#t=", "#x=1", "#t"])("sin token (%s) devuelve null", (hash) => {
    expect(takeToken(loc(hash), { replaceState: vi.fn() })).toBeNull();
  });

  it("aunque no haya token, limpia cualquier fragmento", () => {
    const history = { replaceState: vi.fn() };
    takeToken(loc("#algo"), history);
    expect(history.replaceState).toHaveBeenCalled();
  });

  it("no toca el historial si no hay fragmento", () => {
    const history = { replaceState: vi.fn() };
    takeToken(loc(""), history);
    expect(history.replaceState).not.toHaveBeenCalled();
  });

  it("un fragmento mal codificado no rompe", () => {
    expect(takeToken(loc("#t=%E0%A4%A"), { replaceState: vi.fn() })).toBeNull();
  });
});

describe("requestIdFromPath", () => {
  it("extrae el identificador", () => {
    expect(requestIdFromPath(`/sign/${ID}`)).toBe(ID);
    expect(requestIdFromPath(`/sign/${ID}/`)).toBe(ID);
  });

  it.each(["/", "/sign/", "/sign/no-es-uuid", `/otra/${ID}`, `/sign/${ID}/extra`, `/sign/${ID}x`])(
    "rechaza %s",
    (path) => {
      expect(requestIdFromPath(path)).toBeNull();
    },
  );
});

describe("newSessionRef", () => {
  it("es hexadecimal, de 32 caracteres y distinto cada vez", () => {
    const a = newSessionRef();
    const b = newSessionRef();
    expect(a).toMatch(/^[0-9a-f]{32}$/);
    expect(a).not.toBe(b);
  });
});

describe("applyTheme", () => {
  it("fija el tema que pide el anfitrión y lo quita con un valor desconocido o ausente", () => {
    const root = { dataset: {} as DOMStringMap };
    expect(applyTheme(root, "?theme=dark")).toBe("dark");
    expect(root.dataset.theme).toBe("dark");
    expect(applyTheme(root, "?theme=light")).toBe("light");
    expect(root.dataset.theme).toBe("light");
    expect(applyTheme(root, "?theme=verde")).toBeNull();
    expect(root.dataset.theme).toBeUndefined();
    expect(applyTheme(root, "")).toBeNull();
    expect(root.dataset.theme).toBeUndefined();
  });
});
