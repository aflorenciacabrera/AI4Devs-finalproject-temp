import { ServerError, codeOf, detailOf } from "./errors";
import { isBatchContext, isPrepareResponse, isRetryResponse, isWidgetContext } from "./guards";
import type {
  AgentSignature,
  BatchContextResponse,
  PrepareResponse,
  RetryResponse,
  WidgetContext,
} from "./types";

export interface ServerClient {
  getContext(): Promise<WidgetContext>;
  /** Fija el método de firma elegido (solo con la solicitud `pending`). */
  selectProvider(provider: string): Promise<WidgetContext>;
  /** `certificatePem` solo para el proveedor token; con `local` se llama sin argumentos. */
  prepare(certificatePem?: string): Promise<PrepareResponse>;
  complete(signatures: AgentSignature[]): Promise<WidgetContext>;
  /** El PDF firmado (solicitud) o el ZIP con los firmados (lote). */
  downloadPdf(): Promise<{ blob: Blob; filename: string }>;
  /** Solo en lotes: crea otro lote con los documentos fallidos y devuelve su enlace de firma. */
  retry?(): Promise<RetryResponse>;
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

/** Transporte común: cabeceras de seguridad, tiempo máximo y errores normalizados. */
function createTransport(options: ServerClientOptions, root: string) {
  const { token, sessionRef, timeoutMs = DEFAULT_TIMEOUT_MS } = options;
  const fetchFn = options.fetchFn ?? ((...args: Parameters<typeof fetch>) => fetch(...args));

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

  async function download(path: string, fallbackName: string) {
    const response = await call(path, { method: "GET" });
    const blob = await response.blob();
    const match = /filename="?([^";]+)"?/i.exec(response.headers.get("content-disposition") ?? "");
    return { blob, filename: match?.[1] ?? fallbackName };
  }

  return { call, json, invalid, download };
}

export function createServerClient(options: ServerClientOptions): ServerClient {
  const { requestId, baseUrl = "" } = options;
  const { json, invalid, download } = createTransport(
    options,
    `${baseUrl}/api/v1/widget/requests/${encodeURIComponent(requestId)}`,
  );

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
    downloadPdf: () => download("/download", "documento-firmado.pdf"),
  };
}

const NO_DOCUMENTS = "documentos";

/** El lote como un `WidgetContext`: la máquina de estados y las pantallas se reutilizan sin cambios. */
export function batchToContext(batch: BatchContextResponse): WidgetContext {
  const terminal = ["completed", "partial_failure", "failed"].includes(batch.status);
  const count = batch.documents.length;
  return {
    id: batch.id,
    // Los estados terminales del lote llevan a la pantalla de resultado (que el widget llama `signed`).
    status: terminal ? "signed" : batch.status === "signing" ? "signing" : "pending",
    provider: batch.provider,
    document_name: count === 1 ? (batch.documents[0]?.document_name ?? NO_DOCUMENTS) : `${count} ${NO_DOCUMENTS}`,
    signer_name: batch.signer_name,
    allowed_origins: batch.allowed_origins,
    agent_url: batch.agent_url,
    allowed_providers: batch.allowed_providers,
    token_expires_at: batch.token_expires_at,
    signed_at: batch.completed_at,
    certificate: null,
    document: null,
    batch: { status: batch.status, documents: batch.documents },
  };
}

export function createBatchServerClient(options: ServerClientOptions): ServerClient {
  const { requestId: batchId, baseUrl = "" } = options;
  const { json, invalid, download } = createTransport(
    options,
    `${baseUrl}/api/v1/widget/batches/${encodeURIComponent(batchId)}`,
  );
  const asContext = (body: unknown): WidgetContext => {
    if (!isBatchContext(body)) throw invalid();
    return batchToContext(body);
  };

  return {
    async getContext() {
      return asContext(await json("", { method: "GET" }));
    },
    async selectProvider(provider) {
      return asContext(await json("/provider", { method: "POST", body: { provider } }));
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
      return asContext(await json("/complete", { method: "POST", body: { signatures } }));
    },
    downloadPdf: () => download("/download", "documentos-firmados.zip"),
    async retry() {
      const body = await json("/retry", { method: "POST" });
      if (!isRetryResponse(body)) throw invalid();
      return body;
    },
  };
}
