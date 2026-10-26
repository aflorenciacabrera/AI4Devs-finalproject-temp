import { AgentError, AgentUnreachableError, codeOf, detailOf } from "./errors";
import { isAgentCertificate, isAgentSignatures } from "./guards";
import type { AgentCertificate, AgentSignature, Challenge } from "./types";

export interface AgentClient {
  certificates(): Promise<AgentCertificate[]>;
  sign(certificateId: string, challenges: Challenge[]): Promise<AgentSignature[]>;
}

export interface AgentClientOptions {
  baseUrl: string;
  fetchFn?: typeof fetch;
  /** Detección del agente: debe ser breve. */
  detectTimeoutMs?: number;
  /** El agente espera a la persona (diálogo + PIN): el agente mismo corta a los 120 s. */
  signTimeoutMs?: number;
}

export function createAgentClient(options: AgentClientOptions): AgentClient {
  const { baseUrl, detectTimeoutMs = 8_000, signTimeoutMs = 150_000 } = options;
  const fetchFn = options.fetchFn ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  const root = baseUrl.replace(/\/+$/, "");

  async function call(path: string, init: RequestInit, timeoutMs: number): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let response: Response;
    try {
      response = await fetchFn(`${root}${path}`, {
        ...init,
        mode: "cors",
        credentials: "omit",
        cache: "no-store",
        signal: controller.signal,
      });
    } catch {
      // Sin respuesta: agente cerrado, otro puerto, permiso de red local denegado o tiempo agotado.
      throw new AgentUnreachableError();
    } finally {
      clearTimeout(timer);
    }
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      throw new AgentError(
        codeOf(body, `http_${response.status}`),
        response.status,
        detailOf(body, `el agente respondió ${response.status}`),
      );
    }
    return body;
  }

  const invalid = () => new AgentError("invalid_response", 200, "respuesta inesperada del agente");

  return {
    async certificates() {
      const body = await call("/certificates", { method: "GET" }, detectTimeoutMs);
      const list = (body as { certificates?: unknown } | null)?.certificates;
      if (!Array.isArray(list) || !list.every(isAgentCertificate)) throw invalid();
      return list;
    },
    async sign(certificateId, challenges) {
      const body = await call(
        "/sign",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            certificate_id: certificateId,
            items: challenges.map((c) => ({
              challenge_id: c.challenge_id,
              document_name: c.document_name,
              hash_algorithm: c.hash_algorithm,
              hash_to_sign: c.hash_to_sign,
            })),
          }),
        },
        signTimeoutMs,
      );
      if (!isAgentSignatures(body)) throw invalid();
      return body.signatures;
    },
  };
}
