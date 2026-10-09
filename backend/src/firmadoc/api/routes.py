import uuid

from fastapi import APIRouter, Depends, Response

from ..filenames import attachment_headers
from ..models import Document
from ..services import documents as docs
from ..services import signature_batch as batches
from ..services import signature_flow as flow
from ..services.signature_flow import Ctx
from . import schemas
from .deps import get_ctx, session_ref

router = APIRouter(prefix="/api/v1")


def _session(request_id: uuid.UUID, header: str | None) -> str:
    return header or f"request:{request_id}"


@router.post("/signature-requests", status_code=201, response_model=schemas.SignatureRequestCreated)
def create_signature_request(body: schemas.CreateSignatureRequest, ctx: Ctx = Depends(get_ctx)):
    request = flow.create_request(
        ctx,
        document_base64=body.document_base64,
        document_id=body.document_id,
        external_document_id=body.external_document_id,
        signer_name=body.signer.full_name,
        signer_identifier=body.signer.identifier,
        signer_email=body.signer.email,
        provider=body.provider,
        callback_url=body.callback_url,
        allowed_providers=body.allowed_providers,
    )
    return {
        "id": request.id,
        "document_id": request.document_id,
        "status": request.status.value,
        "signing_url": flow.signing_url(ctx, request),
        "created_at": request.created_at,
    }


@router.post("/signature-requests/{request_id}/prepare", response_model=schemas.PrepareResponse)
def prepare_signature(
    request_id: uuid.UUID,
    body: schemas.PrepareBody | None = None,
    ctx: Ctx = Depends(get_ctx),
    header: str | None = Depends(session_ref),
):
    certificate_pem = body.certificate_pem if body else None
    return flow.prepare(ctx, request_id, certificate_pem, _session(request_id, header))


@router.post("/signature-requests/{request_id}/complete", response_model=schemas.SignatureRequestOut)
def complete_signature(
    request_id: uuid.UUID,
    body: schemas.CompleteBody | None = None,
    ctx: Ctx = Depends(get_ctx),
    header: str | None = Depends(session_ref),
):
    signatures = [(s.challenge_id, s.signature_base64) for s in (body.signatures if body else [])]
    return flow.complete(ctx, request_id, signatures, _session(request_id, header))


@router.get("/signature-requests/{request_id}", response_model=schemas.SignatureRequestOut)
def get_signature_request(request_id: uuid.UUID, ctx: Ctx = Depends(get_ctx)):
    return flow.get_request(ctx, request_id)


@router.get("/documents/{document_id}/versions/{number}/download")
def download_version(document_id: uuid.UUID, number: int, ctx: Ctx = Depends(get_ctx)):
    data = flow.get_version_bytes(ctx, document_id, number)  # verifica que el documento sea del integrador
    document = ctx.db.get(Document, document_id)
    return Response(
        content=data,
        media_type="application/pdf",
        headers=attachment_headers(flow.document_name(document)),  # el nombre original del archivo
    )


def _batch_session(batch_id: uuid.UUID, header: str | None) -> str:
    return header or f"batch:{batch_id}"


@router.post("/signature-batches", status_code=201, response_model=schemas.SignatureBatchOut)
def create_signature_batch(body: schemas.CreateSignatureBatch, ctx: Ctx = Depends(get_ctx)):
    return batches.create_batch(
        ctx,
        documents=[d.model_dump() for d in body.documents],
        signer_name=body.signer.full_name,
        signer_identifier=body.signer.identifier,
        signer_email=body.signer.email,
        provider=body.provider,
        callback_url=body.callback_url,
        allowed_providers=body.allowed_providers,
    )


@router.post("/signature-batches/{batch_id}/prepare", response_model=schemas.BatchPrepareResponse)
def prepare_signature_batch(
    batch_id: uuid.UUID,
    body: schemas.PrepareBody | None = None,
    ctx: Ctx = Depends(get_ctx),
    header: str | None = Depends(session_ref),
):
    certificate_pem = body.certificate_pem if body else None
    return batches.prepare(ctx, batch_id, certificate_pem, _batch_session(batch_id, header))


@router.post("/signature-batches/{batch_id}/complete", response_model=schemas.SignatureBatchOut)
def complete_signature_batch(
    batch_id: uuid.UUID,
    body: schemas.CompleteBody | None = None,
    ctx: Ctx = Depends(get_ctx),
    header: str | None = Depends(session_ref),
):
    signatures = [(s.challenge_id, s.signature_base64) for s in (body.signatures if body else [])]
    return batches.complete(ctx, batch_id, signatures, _batch_session(batch_id, header))


@router.get("/signature-batches/{batch_id}", response_model=schemas.SignatureBatchOut)
def get_signature_batch(batch_id: uuid.UUID, ctx: Ctx = Depends(get_ctx)):
    return batches.get_batch(ctx, batch_id)


@router.get("/documents/{document_id}", response_model=schemas.DocumentOut)
def get_document(document_id: uuid.UUID, ctx: Ctx = Depends(get_ctx)):
    return docs.get_document(ctx, document_id)


@router.patch("/documents/{document_id}", response_model=schemas.DocumentOut)
def update_document(document_id: uuid.UUID, body: schemas.UpdateDocument, ctx: Ctx = Depends(get_ctx)):
    return docs.update_document(ctx, document_id, body.model_dump(exclude_unset=True))


@router.get("/documents/{document_id}/signatures", response_model=list[schemas.SignatureEntry])
def list_document_signatures(document_id: uuid.UUID, ctx: Ctx = Depends(get_ctx)):
    return docs.list_signatures(ctx, document_id)


@router.post("/documents/{document_id}/verify", response_model=schemas.VerifyOut)
def verify_document(document_id: uuid.UUID, ctx: Ctx = Depends(get_ctx)):
    return docs.verify_document(ctx, document_id)
