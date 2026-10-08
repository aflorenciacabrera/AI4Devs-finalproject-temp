import { ServerError, codeOf, detailOf } from "./errors";
import { isPrepareResponse, isWidgetContext } from "./guards";
import type { AgentSignature, PrepareResponse, WidgetContext } from "./types";

export interface ServerClient {
  getContext(): Promise<WidgetContext>;
  /** Fija el método de firma elegido (solo con la solicitud `pending`). */
  selectProvider(provider: string): Promise<WidgetContext>;
  /** `certificatePem` solo para el proveedor token; con `local` se llama sin argumentos. */
  prepare(certificatePem?: string): Promise<PrepareResponse>;
  complete(signatures: AgentSignature[]): Promise<WidgetContext>;
  downloadPdf(): Promise<{ blob: Blob; filename: string }>;
}

export interface ServerClientOptions {
  requestId: string;
  token: string;
  /** Identifica esta carga de la página: ata los desafíos a esta sesión del navegador. */
  sessionRef: string;
  baseUrl?: string;
  fetchFn?: typeof fetch;
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 30_000;

export function createServerClient(options: ServerClientOptions): ServerClient {
  const { requestId, token, sessionRef, baseUrl = "", timeoutMs = DEFAULT_TIMEOUT_MS } = options;
  const fetchFn = options.fetchFn ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  const root = `${baseUrl}/api/v1/widget/requests/${encodeURIComponent(requestId)}`;

  async function call(path: string, init: { method: string; body?: unknown }): Promise<Response> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let response: Response;
    try {
      response = await fetchFn(`${root}${path}`, {
        method: init.method,
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Session-Ref": sessionRef,
          ...(init.body !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
        cache: "no-store",
        credentials: "omit",
        signal: controller.signal,
      });
    } catch {
      throw new ServerError("network_error", 0, "no se pudo contactar al servidor de Firmadoc");
    } finally {
      clearTimeout(timer);
    }
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      throw new ServerError(
        codeOf(body, `http_${response.status}`),
        response.status,
        detailOf(body, `el servidor respondió ${response.status}`),
      );
    }
    return response;
  }

  async function json(path: string, init: { method: string; body?: unknown }): Promise<unknown> {
    const response = await call(path, init);
    try {
      return await response.json();
    } catch {
      throw new ServerError("invalid_response", response.status, "respuesta ilegible del servidor");
    }
  }

  const invalid = () => new ServerError("invalid_response", 200, "respuesta inesperada del servidor");

  return {
    async getContext() {
      const body = await json("", { method: "GET" });
      if (!isWidgetContext(body)) throw invalid();
      return body;
    },
    async selectProvider(provider) {
      const body = await json("/provider", { method: "POST", body: { provider } });
      if (!isWidgetContext(body)) throw invalid();
      return body;
    },
    async prepare(certificatePem) {
      const body = await json("/prepare", {
        method: "POST",
        body: certificatePem ? { certificate_pem: certificatePem } : {},
      });
      if (!isPrepareResponse(body)) throw invalid();
      return body;
    },
    async complete(signatures) {
      const body = await json("/complete", { method: "POST", body: { signatures } });
      if (!isWidgetContext(body)) throw invalid();
      return body;
    },
    async downloadPdf() {
      const response = await call("/download", { method: "GET" });
      const blob = await response.blob();
      const match = /filename="?([^";]+)"?/i.exec(response.headers.get("content-disposition") ?? "");
      return { blob, filename: match?.[1] ?? "documento-firmado.pdf" };
    },
  };
}
