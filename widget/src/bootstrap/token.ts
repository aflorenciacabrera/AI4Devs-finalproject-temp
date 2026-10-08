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

/** Identifica esta carga de la página; ata los desafíos de firma a esta sesión del navegador. */
export function newSessionRef(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
