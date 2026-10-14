/**
 * El token del widget llega en el fragmento de la URL (`#t=...`): el navegador no lo envía al servidor.
 * Se lee una sola vez, se borra de la barra de direcciones y del historial, y vive solo en memoria.
 */

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function takeToken(
  location: Pick<Location, "hash" | "pathname" | "search">,
  history: Pick<History, "replaceState">,
): string | null {
  const hash = location.hash.replace(/^#/, "");
  let token: string | null = null;
  for (const part of hash.split("&")) {
    const [key, ...rest] = part.split("=");
    if (key === "t" && rest.length > 0) {
      try {
        token = decodeURIComponent(rest.join("="));
      } catch {
        token = null;
      }
    }
  }
  if (location.hash) {
    history.replaceState(null, "", location.pathname + location.search);
  }
  return token && token.length > 0 ? token : null;
}

/** `/sign/{uuid}` → el identificador de la solicitud. */
export function requestIdFromPath(pathname: string): string | null {
  const match = /^\/sign\/([^/]+)\/?$/.exec(pathname);
  const candidate = match?.[1];
  return candidate && UUID.test(candidate) ? candidate : null;
}

export type SigningLink = { kind: "request" | "batch"; id: string };

/** `/sign/{uuid}` (una solicitud) o `/sign/batch/{uuid}` (un lote). */
export function linkFromPath(pathname: string): SigningLink | null {
  const batch = /^\/sign\/batch\/([^/]+)\/?$/.exec(pathname)?.[1];
  if (batch !== undefined) return UUID.test(batch) ? { kind: "batch", id: batch } : null;
  const id = requestIdFromPath(pathname);
  return id ? { kind: "request", id } : null;
}

/** Identifica esta carga de la página; ata los desafíos de firma a esta sesión del navegador. */
export function newSessionRef(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Tema que pide el anfitrión con `?theme=light|dark` (el panel pasa el suyo). Otro valor o ninguno: sin
 * atributo, y los estilos siguen el esquema del sistema.
 */
export function applyTheme(root: { dataset: DOMStringMap }, search: string): "light" | "dark" | null {
  const value = new URLSearchParams(search).get("theme");
  if (value === "light" || value === "dark") {
    root.dataset.theme = value;
    return value;
  }
  delete root.dataset.theme;
  return null;
}
