import type { BatchDocument, WidgetContext } from "../api/types";
import { formatDate, formatDocumentMeta } from "../format";

/** Tarjeta del documento a firmar: nombre, páginas, tamaño y estado con su vencimiento. */
export function DocumentCard({ context }: { context: WidgetContext }) {
  const meta = formatDocumentMeta(context.page_count, context.size_bytes);
  const pending = context.status === "pending" || context.status === "signing";
  return (
    <div className="doc-card" aria-label="Documento a firmar">
      <div className="doc-card__main">
        <span className="doc-card__label">Documento a firmar</span>
        <strong className="doc-card__name">{context.document_name}</strong>
        {meta ? <span className="doc-card__meta">{meta}</span> : null}
      </div>
      {pending ? (
        <div className="doc-card__status">
          <span className="badge badge--amber">Pendiente de firma</span>
          {context.signature_deadline ? <small>Vence {formatDate(context.signature_deadline)}</small> : null}
        </div>
      ) : null}
    </div>
  );
}

/** Lista de documentos de un lote antes de firmar. */
export function BatchDocumentList({ documents }: { documents: BatchDocument[] }) {
  return (
    <section className="batch-list" aria-label={`Documentos a firmar (${documents.length})`}>
      <h2 className="batch-list__title">
        Documentos a firmar ({documents.length})
        <span className="batch-list__count">{documents.length} seleccionados</span>
      </h2>
      <ul>
        {documents.map((d) => {
          const meta = formatDocumentMeta(d.page_count, d.size_bytes);
          return (
            <li key={d.signature_request_id}>
              <strong>{d.document_name}</strong>
              {meta ? <span>{meta}</span> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
