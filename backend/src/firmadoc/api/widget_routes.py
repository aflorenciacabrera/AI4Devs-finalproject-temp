"""Endpoints del widget: autenticados con el token de la solicitud, no con la API key.

Reutilizan los casos de uso de `signature_flow`; solo cambia cómo se autentica quien llama.
"""

import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from .. import signing_token
from ..config import Settings
from ..errors import NotFound
from ..filenames import attachment_headers
from ..models import Document, IntegratingSystem, SignatureRequest
from ..services import signature_flow as flow
from ..services import widget as widget_service
from ..services.signature_flow import Ctx
from ..storage import DocumentStorage
from . import schemas
from .deps import get_db, get_storage, session_ref, settings_dep

router = APIRouter(prefix="/api/v1/widget")


@dataclass
class WidgetAuth:
    ctx: Ctx
    request: SignatureRequest
    token_exp: int


def widget_auth(
    request_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    storage: DocumentStorage = Depends(get_storage),
    settings: Settings = Depends(settings_dep),
) -> WidgetAuth:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise signing_token.invalid()
    payload = signing_token.verify(signing_token.secret_for(settings), token.strip(), request_id)
    request = db.get(SignatureRequest, request_id)
    if request is None:
        raise NotFound("solicitud de firma inexistente")
    system = db.get(IntegratingSystem, request.integrating_system_id)
    return WidgetAuth(Ctx(db, storage, settings, system), request, payload["exp"])


def _session(request_id: uuid.UUID, header: str | None) -> str:
    return header or f"request:{request_id}"


@router.get("/requests/{request_id}", response_model=schemas.WidgetContext)
def get_context(auth: WidgetAuth = Depends(widget_auth)):
    return widget_service.widget_context(auth.ctx, auth.request, auth.token_exp)


@router.post("/requests/{request_id}/provider", response_model=schemas.WidgetContext)
def select_provider(
    request_id: uuid.UUID,
    body: schemas.SelectProviderBody,
    auth: WidgetAuth = Depends(widget_auth),
):
    widget_service.select_provider(auth.ctx, auth.request, body.provider)
    return widget_service.widget_context(auth.ctx, auth.request, auth.token_exp)


@router.post("/requests/{request_id}/prepare", response_model=schemas.PrepareResponse)
def prepare(
    request_id: uuid.UUID,
    body: schemas.PrepareBody | None = None,
    auth: WidgetAuth = Depends(widget_auth),
    header: str | None = Depends(session_ref),
):
    certificate_pem = body.certificate_pem if body else None
    return flow.prepare(auth.ctx, request_id, certificate_pem, _session(request_id, header))


@router.post("/requests/{request_id}/complete", response_model=schemas.WidgetContext)
def complete(
    request_id: uuid.UUID,
    body: schemas.CompleteBody | None = None,
    auth: WidgetAuth = Depends(widget_auth),
    header: str | None = Depends(session_ref),
):
    signatures = [(s.challenge_id, s.signature_base64) for s in (body.signatures if body else [])]
    flow.complete(auth.ctx, request_id, signatures, _session(request_id, header))
    request = widget_service.load_request(auth.ctx, request_id)
    return widget_service.widget_context(auth.ctx, request, auth.token_exp)


@router.get("/requests/{request_id}/download")
def download(request_id: uuid.UUID, auth: WidgetAuth = Depends(widget_auth)):
    data, _number = widget_service.signed_pdf(auth.ctx, auth.request)
    document = auth.ctx.db.get(Document, auth.request.document_id)
    return Response(
        content=data,
        media_type="application/pdf",
        headers=attachment_headers(flow.document_name(document)),  # el nombre original del archivo
    )
