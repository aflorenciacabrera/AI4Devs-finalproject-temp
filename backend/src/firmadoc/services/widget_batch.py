"""Casos de uso del widget para lotes: contexto, elección de método, descarga de los firmados y reintento."""

import tempfile
import uuid
from datetime import UTC, datetime
from typing import IO

from sqlalchemy import select

from ..errors import Conflict, Unprocessable
from ..filenames import unique_name
from ..models import (
    AuditEvent,
    Document,
    DocumentVersion,
    Provider,
    RequestStatus,
    SignatureBatch,
    SignatureRequest,
    Signer,
)
from ..providers import get_provider
from . import signature_batch as batches
from . import signature_flow as flow
from .signature_flow import Ctx
from .widget import allowed_origins

ZIP_SPOOL_BYTES = 32 * 1024 * 1024  # por encima de esto el ZIP se arma en disco, no en memoria


def available_providers(ctx: Ctx, batch: SignatureBatch) -> list[Provider]:
    """Métodos que la persona puede elegir en el lote: los permitidos y habilitados (el activo se informa siempre)."""
    configured = [p for p in (batch.allowed_providers or "").split(",") if p]
    candidates = [Provider(p) for p in configured] or [batch.provider]
    enabled = []
    for provider in candidates:
        try:
            get_provider(provider, ctx.settings)
        except Unprocessable:
            if provider == batch.provider:
                enabled.append(provider)
            continue
        enabled.append(provider)
    return enabled


def _signed_version(ctx: Ctx, request: SignatureRequest) -> DocumentVersion | None:
    return ctx.db.scalar(select(DocumentVersion).where(DocumentVersion.signature_request_id == request.id))


def _item(ctx: Ctx, request: SignatureRequest, error: dict | None) -> dict:
    document = ctx.db.get(Document, request.document_id)
    pages, size = flow.document_stats(ctx, document)
    version = _signed_version(ctx, request)
    return {
        "signature_request_id": request.id,
        "document_id": request.document_id,
        "document_name": flow.document_name(document),
        "page_count": pages,
        "size_bytes": size,
        "status": request.status.value,
        "version_number": version.version_number if version else None,
        "error": error,
    }


def batch_context(
    ctx: Ctx, batch: SignatureBatch, token_exp: int, errors: dict[uuid.UUID, dict] | None = None
) -> dict:
    """El lote para el widget: sin binarios ni token. `errors` solo viene de la respuesta de `complete`."""
    errors = errors or {}
    ctx.db.refresh(batch)
    requests = batches._requests(ctx, batch)
    signer = ctx.db.get(Signer, batch.signer_id)
    return {
        "id": batch.id,
        "status": batch.status.value,
        "provider": batch.provider.value,
        "allowed_providers": [p.value for p in available_providers(ctx, batch)],
        "signer_name": signer.full_name,
        "allowed_origins": allowed_origins(ctx.system),
        "agent_url": ctx.settings.agent_url,
        "token_expires_at": datetime.fromtimestamp(token_exp, UTC),
        "completed_at": batch.completed_at,
        "documents": [_item(ctx, r, errors.get(r.id)) for r in requests],
    }


def select_provider(ctx: Ctx, batch: SignatureBatch, provider: Provider) -> None:
    pending = [r for r in batches._requests(ctx, batch) if r.status == RequestStatus.PENDING]
    if batch.status != batches.BatchStatus.PENDING or len(pending) != len(batches._requests(ctx, batch)):
        raise Conflict(f"el lote está en estado '{batch.status.value}': no se puede cambiar el método")
    if provider not in available_providers(ctx, batch):
        raise Unprocessable("ese método de firma no está disponible para este lote", code="provider_not_allowed")
    if provider == batch.provider:
        return
    previous = batch.provider
    batch.provider = provider
    for request in pending:
        request.provider = provider
    ctx.db.add(
        AuditEvent(
            batch_id=batch.id,
            event_type="provider_selected",
            payload={"from": previous.value, "to": provider.value},
        )
    )
    ctx.db.commit()


def signed_zip(ctx: Ctx, batch: SignatureBatch) -> tuple[IO[bytes], int]:
    """ZIP con el PDF vigente de cada documento firmado del lote. Devuelve el archivo (posicionado al inicio) y su tamaño."""
    import zipfile

    signed = []
    for request in batches._requests(ctx, batch):
        version = _signed_version(ctx, request)
        if request.status == RequestStatus.SIGNED and version is not None:
            signed.append((request, version))
    if not signed:
        raise Conflict("el lote no tiene documentos firmados")

    spool = tempfile.SpooledTemporaryFile(max_size=ZIP_SPOOL_BYTES)  # noqa: SIM115 - lo cierra quien lo consume
    used: set[str] = set()
    with zipfile.ZipFile(spool, "w", zipfile.ZIP_STORED) as archive:
        for request, version in signed:
            document = ctx.db.get(Document, request.document_id)
            # Cada PDF con su nombre original; si dos se llaman igual, el segundo lleva «-2», «-3»…
            name = unique_name(flow.document_name(document), used)
            archive.writestr(name, ctx.storage.read(version.storage_ref))
    size = spool.tell()
    spool.seek(0)
    return spool, size


def retry(ctx: Ctx, batch: SignatureBatch) -> dict:
    """Crea otro lote solo con los documentos fallidos (mismo firmante y métodos). Los firmados no entran."""
    if batch.status not in batches.TERMINAL:
        raise Conflict("el lote todavía no terminó")
    requests = batches._requests(ctx, batch)
    failed = [r for r in requests if r.status == RequestStatus.FAILED]
    if not failed:
        raise Conflict("el lote no tiene documentos fallidos")
    signer = ctx.db.get(Signer, batch.signer_id)
    allowed = [Provider(p) for p in (batch.allowed_providers or "").split(",") if p] or None
    created = batches.create_batch(
        ctx,
        documents=[{"document_id": r.document_id} for r in failed],
        signer_name=signer.full_name,
        signer_identifier=signer.identifier,
        signer_email=signer.email,
        provider=batch.provider,
        callback_url=failed[0].callback_url,
        allowed_providers=allowed,
    )
    return {"id": created["id"], "signing_url": created["signing_url"]}
