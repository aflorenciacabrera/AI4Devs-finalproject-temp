/**
 * Mensajes hacia la página anfitriona: la que embebe el widget (`window.parent`) o, si el widget corre en
 * una ventana propia abierta con `window.open`, la que lo abrió (`window.opener`).
 *
 * El widget no puede conocer con certeza el origen de su anfitrión, pero sí los `allowed_origins` del
 * integrador (los únicos que pueden enmarcarlo, por la CSP `frame-ancestors`). Cada mensaje se envía
 * una vez a cada origen permitido y el navegador lo entrega solo al que coincida con el real: nunca `"*"`.
 * Por eso una ventana abierta desde otro origen tampoco recibe nada.
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
  | "firmadoc:closed"
  | "firmadoc:resize";

export interface HostNotifier {
  ready(): void;
  signed(document: DocumentBlock | null): void;
  batchCompleted(batch: BatchInfo, batchId: string): void;
  failed(code: string): void;
  cancelled(): void;
  closed(): void;
  /** Alto del contenido en píxeles, para que el diálogo anfitrión se ajuste. */
  resized(height: number): void;
}

type PostTarget = Pick<Window, "postMessage"> & { closed?: boolean };

/** `parent`: embebido en un iframe. `opener`: en una ventana propia abierta por la anfitriona. */
export type HostKind = "parent" | "opener";

export interface HostWindow {
  target: PostTarget;
  kind: HostKind;
}

/** La ventana anfitriona, si hay: el marco padre gana sobre un `opener` heredado. */
export function findHostWindow(): HostWindow | null {
  if (typeof window === "undefined") return null;
  if (window.parent !== window) return { target: window.parent, kind: "parent" };
  const opener = window.opener as Window | null;
  if (opener && !opener.closed) return { target: opener, kind: "opener" };
  return null; // pestaña abierta a mano o con `noopener`: nadie a quien avisar
}

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

function resolveHost(host: HostWindow | PostTarget | null): HostWindow | null {
  if (host === null) return null;
  if ("target" in host && "kind" in host) return host;
  return { target: host, kind: "parent" };
}

export function createHostNotifier(
  allowedOrigins: string[],
  requestId: string,
  host: HostWindow | PostTarget | null = findHostWindow(),
  closeWindow: () => void = () => {
    if (typeof window !== "undefined") window.close();
  },
): HostNotifier {
  const resolved = resolveHost(host);
  const send = (type: HostMessageType, extra: Record<string, unknown> = {}) => {
    if (!resolved) return; // sin página anfitriona (ventana propia abierta a mano)
    if (resolved.kind === "opener" && resolved.target.closed) return; // la anfitriona ya se cerró
    const message = { source: "firmadoc", type, requestId, ...extra };
    for (const origin of allowedOrigins) {
      if (origin && origin !== "*") resolved.target.postMessage(message, origin);
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
    closed: () => {
      send("firmadoc:closed");
      if (resolved?.kind === "opener") closeWindow(); // en una ventana propia, «Cerrar» la cierra
    },
    resized: (height: number) => {
      if (!Number.isFinite(height) || height < 1) return;
      send("firmadoc:resize", { height: Math.min(4000, Math.ceil(height)) });
    },
  };
}

export const silentNotifier: HostNotifier = {
  ready() {},
  signed() {},
  batchCompleted() {},
  failed() {},
  cancelled() {},
  closed() {},
  resized() {},
};
