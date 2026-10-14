import { useState } from "react";

import type { WidgetContext } from "../api/types";
import { Button } from "../components/Notice";
import { Screen } from "../components/Screen";
import { commonName, formatDateTime } from "../format";
import { providerLabel } from "../messages/es";

interface Props {
  context: WidgetContext;
  onDownload: () => Promise<void>;
  onClose: () => void;
}

export function Success({ context, onDownload, onClose }: Props) {
  const [downloading, setDownloading] = useState(false);
  const [downloadFailed, setDownloadFailed] = useState(false);
  const { document, certificate } = context;

  async function download() {
    setDownloading(true);
    setDownloadFailed(false);
    try {
      await onDownload();
    } catch {
      setDownloadFailed(true);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Screen
      title="Documento firmado correctamente"
      subtitle="Firma completada"
      tone="success"
      actions={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cerrar
          </Button>
          <Button onClick={() => void download()} disabled={downloading}>
            {downloading ? "Descargando…" : "Descargar PDF firmado"}
          </Button>
        </>
      }
    >
      {downloadFailed ? (
        <p className="alert alert--error" role="alert">
          No se pudo descargar el PDF. Reintentá en unos instantes.
        </p>
      ) : null}
      <dl className="kv">
        <dt>Documento</dt>
        <dd>{context.document_name}</dd>
        <dt>Firmante</dt>
        <dd>{context.signer_name}</dd>
        {context.signed_at ? (
          <>
            <dt>Fecha y hora</dt>
            <dd>{formatDateTime(context.signed_at)}</dd>
          </>
        ) : null}
        <dt>Método</dt>
        <dd>{providerLabel(context.provider)}</dd>
        {document?.signature_level ? (
          <>
            <dt>Nivel de firma</dt>
            <dd>PAdES {document.signature_level}</dd>
          </>
        ) : null}
        {certificate ? (
          <>
            <dt>Certificado</dt>
            <dd>
              {commonName(certificate.subject)}
              <small className="mono">
                Emisor: {commonName(certificate.issuer_subject)} · Serie {certificate.serial_number}
              </small>
            </dd>
          </>
        ) : null}
        {document ? (
          <>
            <dt>Versión del documento</dt>
            <dd>
              v{document.version_number}
              {document.is_active_version ? " · vigente" : ""}
            </dd>
          </>
        ) : null}
      </dl>
    </Screen>
  );
}
