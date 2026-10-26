import { useState } from "react";

import type { BatchDocument, WidgetContext } from "../api/types";
import { Button } from "../components/Notice";
import { Screen } from "../components/Screen";
import { formatDateTime } from "../format";
import { failureMessage, providerLabel } from "../messages/es";

interface Props {
  context: WidgetContext;
  onDownload: () => Promise<void>;
  onRetry: () => Promise<void>;
  onClose: () => void;
}

function itemStatus(d: BatchDocument): string {
  if (d.status === "signed") return d.version_number ? `Firmado · v${d.version_number}` : "Firmado";
  if (d.status === "failed") {
    const reason = failureMessage(d.error?.code ?? `http_${d.error?.http_status ?? 0}`).body;
    return d.error ? `Error: ${reason} (${d.error.http_status})` : "Error: no se pudo firmar";
  }
  return "Pendiente: la firma no se completó";
}

/** Resultado de la firma de un lote: cuántos se firmaron, el estado de cada uno, descarga y reintento. */
export function BatchResult({ context, onDownload, onRetry, onClose }: Props) {
  const documents = context.batch?.documents ?? [];
  const signed = documents.filter((d) => d.status === "signed").length;
  const failed = documents.filter((d) => d.status === "failed").length;
  const [busy, setBusy] = useState<"download" | "retry" | null>(null);
  const [problem, setProblem] = useState<"download" | "retry" | null>(null);

  async function run(kind: "download" | "retry", action: () => Promise<void>) {
    setBusy(kind);
    setProblem(null);
    try {
      await action();
    } catch {
      setProblem(kind);
    } finally {
      setBusy(null);
    }
  }

  const allSigned = signed === documents.length && documents.length > 0;
  return (
    <Screen
      title={allSigned ? "Firma en lote completada" : "Firma en lote finalizada"}
      subtitle={`${signed} de ${documents.length} documentos firmados`}
      announce={`${signed} de ${documents.length} documentos firmados`}
      tone={allSigned ? "success" : "default"}
      actions={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cerrar
          </Button>
          {failed > 0 ? (
            <Button variant="secondary" onClick={() => void run("retry", onRetry)} disabled={busy !== null}>
              {busy === "retry" ? "Preparando…" : `Reintentar (${failed})`}
            </Button>
          ) : null}
          {signed > 0 ? (
            <Button onClick={() => void run("download", onDownload)} disabled={busy !== null}>
              {busy === "download" ? "Descargando…" : `Descargar firmados (${signed})`}
            </Button>
          ) : null}
        </>
      }
    >
      <p>
        {signed > 0
          ? `Los ${signed} firmados ya quedaron como nueva versión vigente.`
          : "No se firmó ningún documento."}
        {failed > 0 ? " Podés reintentar solo los que fallaron." : ""}
      </p>
      {problem ? (
        <p className="alert alert--error" role="alert">
          {problem === "download"
            ? "No se pudo descargar los documentos. Reintentá en unos instantes."
            : "No se pudo preparar el reintento. Reintentá en unos instantes."}
        </p>
      ) : null}
      <dl className="kv">
        <dt>Firmante</dt>
        <dd>{context.signer_name}</dd>
        <dt>Método</dt>
        <dd>{providerLabel(context.provider)}</dd>
        {context.signed_at ? (
          <>
            <dt>Fecha y hora</dt>
            <dd>{formatDateTime(context.signed_at)}</dd>
          </>
        ) : null}
      </dl>
      <ul className="result-list">
        {documents.map((d) => (
          <li key={d.signature_request_id} className={`result-item result-item--${d.status}`}>
            <strong>{d.document_name}</strong>
            <span>{itemStatus(d)}</span>
          </li>
        ))}
      </ul>
    </Screen>
  );
}
