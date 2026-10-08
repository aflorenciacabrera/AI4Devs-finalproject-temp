"""Endpoints del widget para lotes: autenticados con el token del lote, no con la API key.

Reutilizan los casos de uso de `signature_batch`; solo cambia cómo se autentica quien llama.
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import IO

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import signing_token
from ..config import Settings
from ..errors import NotFound
from ..models import IntegratingSystem, SignatureBatch
from ..services import signature_batch as batches
from ..services import widget_batch
from ..services.signature_flow import Ctx
from ..storage import DocumentStorage
from . import schemas
from .deps import get_db, get_storage, session_ref, settings_dep

router = APIRouter(prefix="/api/v1/widget/batches")


@dataclass
class BatchAuth:
    ctx: Ctx
    batch: SignatureBatch
    token_exp: int


def batch_auth(
    batch_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    storage: DocumentStorage = Depends(get_storage),
    settings: Settings = Depends(settings_dep),
) -> BatchAuth:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise signing_token.invalid()
    payload = signing_token.verify(signing_token.secret_for(settings), token.strip(), batch_id)
    batch = db.get(SignatureBatch, batch_id)
    if batch is None:
        raise NotFound("lote de firma inexistente")
    system = db.get(IntegratingSystem, batch.integrating_system_id)
    return BatchAuth(Ctx(db, storage, settings, system), batch, payload["exp"])


def _session(batch_id: uuid.UUID, header: str | None) -> str:
    return header or f"batch:{batch_id}"


@router.get("/{batch_id}", response_model=schemas.WidgetBatchContext)
def get_context(auth: BatchAuth = Depends(batch_auth)):
    return widget_batch.batch_context(auth.ctx, auth.batch, auth.token_exp)


@router.post("/{batch_id}/provider", response_model=schemas.WidgetBatchContext)
def select_provider(body: schemas.SelectProviderBody, auth: BatchAuth = Depends(batch_auth)):
    widget_batch.select_provider(auth.ctx, auth.batch, body.provider)
    return widget_batch.batch_context(auth.ctx, auth.batch, auth.token_exp)


@router.post("/{batch_id}/prepare", response_model=schemas.BatchPrepareResponse)
def prepare(
    batch_id: uuid.UUID,
    body: schemas.PrepareBody | None = None,
    auth: BatchAuth = Depends(batch_auth),
    header: str | None = Depends(session_ref),
):
    certificate_pem = body.certificate_pem if body else None
    return batches.prepare(auth.ctx, batch_id, certificate_pem, _session(batch_id, header))


@router.post("/{batch_id}/complete", response_model=schemas.WidgetBatchContext)
def complete(
    batch_id: uuid.UUID,
    body: schemas.CompleteBody | None = None,
    auth: BatchAuth = Depends(batch_auth),
    header: str | None = Depends(session_ref),
):
    signatures = [(s.challenge_id, s.signature_base64) for s in (body.signatures if body else [])]
    result = batches.complete(auth.ctx, batch_id, signatures, _session(batch_id, header))
    errors = {item["signature_request_id"]: item["error"] for item in result["requests"] if item["error"]}
    return widget_batch.batch_context(auth.ctx, auth.batch, auth.token_exp, errors)


def _chunks(file: IO[bytes]) -> Iterator[bytes]:
    try:
        while chunk := file.read(1024 * 1024):
            yield chunk
    finally:
        file.close()


@router.get("/{batch_id}/download")
def download(auth: BatchAuth = Depends(batch_auth)):
    archive, size = widget_batch.signed_zip(auth.ctx, auth.batch)
    return StreamingResponse(
        _chunks(archive),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="documentos-firmados.zip"',
            "Content-Length": str(size),
            "Cache-Control": "no-store",
        },
    )


@router.post("/{batch_id}/retry", status_code=201, response_model=schemas.RetryOut)
def retry(auth: BatchAuth = Depends(batch_auth)):
    return widget_batch.retry(auth.ctx, auth.batch)
