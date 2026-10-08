/** Errores normalizados: siempre un `code` estable (nunca texto crudo del servidor para el usuario). */

export class ServerError extends Error {
  constructor(
    readonly code: string,
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail);
    this.name = "ServerError";
  }
}

/** El agente respondió con un error de negocio (`{code, detail}`). */
export class AgentError extends Error {
  constructor(
    readonly code: string,
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail);
    this.name = "AgentError";
  }
}

/** No hubo respuesta del agente: no está abierto, el puerto es otro o el navegador lo bloqueó. */
export class AgentUnreachableError extends Error {
  constructor(message = "no se pudo contactar al agente") {
    super(message);
    this.name = "AgentUnreachableError";
  }
}

export function detailOf(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export function codeOf(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "code" in body) {
    const code = (body as { code: unknown }).code;
    if (typeof code === "string" && code) return code;
  }
  return fallback;
}
