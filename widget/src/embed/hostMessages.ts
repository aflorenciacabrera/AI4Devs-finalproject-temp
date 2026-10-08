/**
 * Mensajes hacia la página que embebe el widget.
 *
 * El widget no puede conocer con certeza el origen de su padre, pero sí los `allowed_origins` del
 * integrador (los únicos que pueden enmarcarlo, por la CSP `frame-ancestors`). Cada mensaje se envía
 * una vez a cada origen permitido y el navegador lo entrega solo al que coincida con el real: nunca `"*"`.
 *
 * No hay mensajes entrantes: el widget no registra ningún listener de `message`.
 */

import type { BatchInfo, DocumentBlock } from "../api/types";

export type HostMessageType =
  | "firmadoc:ready"
  | "firmadoc:signed"
  | "firmadoc:failed"
  | "firmadoc:batch-completed"
  | "firmadoc:cancelled"
  | "firmadoc:closed";

export interface HostNotifier {
  ready(): void;
  signed(document: DocumentBlock | null): void;
  batchCompleted(batch: BatchInfo, batchId: string): void;
  failed(code: string): void;
  cancelled(): void;
  closed(): void;
}

type PostTarget = Pick<Window, "postMessage">;

/** Solo lo que el integrador necesita: nada de token, PDF ni firmas. */
function publicDocument(document: DocumentBlock): Record<string, unknown> {
  return {
    id: document.id,
    version_number: document.version_number,
    is_active_version: document.is_active_version,
    signing_status: document.signing_status,
    signature_level: document.signature_level,
  };
}

export function createHostNotifier(
  allowedOrigins: string[],
  requestId: string,
  parent: PostTarget | null = typeof window !== "undefined" && window.parent !== window ? window.parent : null,
): HostNotifier {
  const send = (type: HostMessageType, extra: Record<string, unknown> = {}) => {
    if (!parent) return; // sin página anfitriona (ventana propia)
    const message = { source: "firmadoc", type, requestId, ...extra };
    for (const origin of allowedOrigins) {
      if (origin && origin !== "*") parent.postMessage(message, origin);
    }
  };
  return {
    ready: () => send("firmadoc:ready"),
    signed: (document) => send("firmadoc:signed", { document: document ? publicDocument(document) : null }),
    failed: (code) => send("firmadoc:failed", { code }),
    batchCompleted: (batch, batchId) =>
      send("firmadoc:batch-completed", {
        batchId,
        status: batch.status,
        signed: batch.documents.filter((d) => d.status === "signed").length,
        total: batch.documents.length,
        documents: batch.documents.map((d) => ({
          document_id: d.document_id,
          status: d.status,
          version_number: d.version_number,
        })),
      }),
    cancelled: () => send("firmadoc:cancelled"),
    closed: () => send("firmadoc:closed"),
  };
}

export const silentNotifier: HostNotifier = {
  ready() {},
  signed() {},
  batchCompleted() {},
  failed() {},
  cancelled() {},
  closed() {},
};
