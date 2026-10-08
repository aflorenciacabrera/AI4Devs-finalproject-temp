"""Lotes de firma: agrupan solicitudes; cada una conserva su flujo, su desafío, su versión y su webhook."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from .. import webhooks
from ..errors import Conflict, DomainError, NotFound, Unprocessable
from ..models import (
    AuditEvent,
    BatchStatus,
    Provider,
    RequestStatus,
    SignatureBatch,
    SignatureRequest,
    SigningChallenge,
)
from . import signature_flow as flow
from .signature_flow import Ctx

TERMINAL = {BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.PARTIAL_FAILURE}


def derive_status(statuses: list[RequestStatus]) -> BatchStatus:
    """Estado del lote a partir del de sus solicitudes."""
    if any(s == RequestStatus.SIGNED for s in statuses):
        return (
            BatchStatus.COMPLETED
            if all(s == RequestStatus.SIGNED for s in statuses)
            else BatchStatus.PARTIAL_FAILURE
        )
    if statuses and all(s == RequestStatus.FAILED for s in statuses):
        return BatchStatus.FAILED
    if any(s == RequestStatus.SIGNING for s in statuses):
        return BatchStatus.SIGNING
    return BatchStatus.PENDING


def _audit(ctx: Ctx, batch: SignatureBatch, event_type: str, payload: dict | None = None) -> None:
    ctx.db.add(AuditEvent(batch_id=batch.id, event_type=event_type, payload=payload or {}))


def _get_batch(ctx: Ctx, batch_id: uuid.UUID) -> SignatureBatch:
    batch = ctx.db.scalar(
        select(SignatureBatch).where(
            SignatureBatch.id == batch_id, SignatureBatch.integrating_system_id == ctx.system.id
        )
    )
    if batch is None:
        raise NotFound("lote de firma inexistente")
    return batch


def _requests(ctx: Ctx, batch: SignatureBatch) -> list[SignatureRequest]:
    return list(
        ctx.db.scalars(
            select(SignatureRequest)
            .where(SignatureRequest.batch_id == batch.id)
            .order_by(SignatureRequest.created_at, SignatureRequest.id)
        )
    )


def _refresh_status(ctx: Ctx, batch: SignatureBatch) -> None:
    ctx.db.expire_all()
    batch = ctx.db.get(SignatureBatch, batch.id)
    batch.status = derive_status([r.status for r in _requests(ctx, batch)])
    if batch.status in TERMINAL:
        batch.completed_at = datetime.now(UTC)


def _item(ctx: Ctx, request: SignatureRequest, error: dict | None = None) -> dict:
    result = flow.request_result(ctx, request, include_bytes=False)
    document = result["document"]
    return {
        "signature_request_id": request.id,
        "document_id": request.document_id,
        "status": request.status.value,
        "version_number": document["version_number"] if document else None,
        "download_url": document["download_url"] if document else None,
        "error": error,
    }


def batch_out(ctx: Ctx, batch: SignatureBatch, errors: dict[uuid.UUID, dict] | None = None) -> dict:
    errors = errors or {}
    return {
        "id": batch.id,
        "status": batch.status.value,
        "provider": batch.provider.value,
        "created_at": batch.created_at,
        "completed_at": batch.completed_at,
        "requests": [_item(ctx, r, errors.get(r.id)) for r in _requests(ctx, batch)],
    }


def create_batch(
    ctx: Ctx,
    *,
    documents: list[dict],
    signer_name: str,
    signer_identifier: str,
    signer_email: str,
    provider: Provider,
    callback_url: str | None,
) -> dict:
    limit = ctx.settings.max_batch_size
    if not 1 <= len(documents) <= limit:
        raise Unprocessable(f"un lote admite entre 1 y {limit} documentos")
    if callback_url is not None:
        webhooks.validate_callback_url(callback_url, ctx.settings)
    db = ctx.db
    try:
        signer = flow.get_or_create_signer(db, signer_name, signer_identifier, signer_email)
        batch = SignatureBatch(
            integrating_system_id=ctx.system.id, signer_id=signer.id, provider=provider
        )
        db.add(batch)
        db.flush()
        for doc in documents:
            flow.create_request(
                ctx,
                document_base64=doc.get("document_base64"),
                document_id=doc.get("document_id"),
                external_document_id=doc.get("external_document_id"),
                signer_name=signer_name,
                signer_identifier=signer_identifier,
                signer_email=signer_email,
                provider=provider,
                callback_url=callback_url,
                batch_id=batch.id,
                commit=False,
            )
        _audit(ctx, batch, "batch_created", {"documents": len(documents), "provider": provider.value})
        db.commit()
    except Exception:
        db.rollback()  # atómico: no queda ninguna fila del lote
        raise
    return batch_out(ctx, batch)


def prepare(ctx: Ctx, batch_id: uuid.UUID, certificate_pem: str | None, session_ref: str) -> dict:
    batch = _get_batch(ctx, batch_id)
    pending = [r for r in _requests(ctx, batch) if r.status in (RequestStatus.PENDING, RequestStatus.SIGNING)]
    if not pending:
        raise Conflict("el lote no tiene solicitudes para preparar")
    challenges = []
    expires = []
    for request in pending:
        prepared = flow.prepare(ctx, request.id, certificate_pem, session_ref)
        challenges.append({**prepared["challenges"][0], "signature_request_id": request.id})
        expires.append(prepared["expires_at"])
    _refresh_status(ctx, batch)
    _audit(ctx, batch, "batch_prepared", {"documents": len(pending)})
    ctx.db.commit()
    return {"challenges": challenges, "expires_at": min(expires)}


def complete(
    ctx: Ctx, batch_id: uuid.UUID, signatures: list[tuple[uuid.UUID, str]], session_ref: str
) -> dict:
    db = ctx.db
    batch = _get_batch(ctx, batch_id)
    requests = _requests(ctx, batch)
    signing = [r for r in requests if r.status == RequestStatus.SIGNING]
    if not signing:
        raise Conflict("el lote no tiene solicitudes preparadas para completar")

    owner: dict[uuid.UUID, uuid.UUID] = {}
    if signatures:
        rows = db.execute(
            select(SigningChallenge.id, SigningChallenge.signature_request_id).where(
                SigningChallenge.id.in_([c for c, _ in signatures])
            )
        )
        owner = {challenge_id: request_id for challenge_id, request_id in rows}
    batch_request_ids = {r.id for r in requests}
    by_request: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
    for challenge_id, signature in signatures:
        request_id = owner.get(challenge_id)
        if request_id not in batch_request_ids:
            raise Conflict("un desafío no pertenece a este lote")
        if request_id in by_request:
            raise Unprocessable("hay más de una firma para la misma solicitud")
        by_request[request_id] = (challenge_id, signature)

    errors: dict[uuid.UUID, dict] = {}
    for request in signing:
        supplied = by_request.get(request.id)
        try:
            flow.complete(
                ctx, request.id, [supplied] if supplied else [], session_ref, include_bytes=False
            )
        except DomainError as e:
            db.rollback()
            errors[request.id] = {"code": e.code, "detail": e.detail, "http_status": e.status_code}

    _refresh_status(ctx, batch)
    signed = sum(1 for r in _requests(ctx, batch) if r.status == RequestStatus.SIGNED)
    _audit(ctx, batch, "batch_completed", {"signed": signed, "errors": len(errors)})
    db.commit()
    return batch_out(ctx, _get_batch(ctx, batch_id), errors)


def get_batch(ctx: Ctx, batch_id: uuid.UUID) -> dict:
    return batch_out(ctx, _get_batch(ctx, batch_id))
