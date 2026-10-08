import uuid

from fastapi import APIRouter, Depends, Response

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
    data = flow.get_version_bytes(ctx, document_id, number)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="documento-v{number}.pdf"'},
    )
