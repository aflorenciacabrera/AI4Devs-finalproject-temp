"""Vista de una solicitud para el widget: solo lo necesario para dibujar la interfaz."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from ..errors import Conflict
from ..models import (
    Certificate,
    Document,
    DocumentVersion,
    IntegratingSystem,
    RequestStatus,
    SignatureRequest,
    Signer,
)
from . import signature_flow as flow
from .signature_flow import Ctx


def allowed_origins(system: IntegratingSystem) -> list[str]:
    return [o.strip() for o in (system.allowed_origins or "").split(",") if o.strip()]


def _signed_version(ctx: Ctx, request: SignatureRequest) -> DocumentVersion | None:
    return ctx.db.scalar(
        select(DocumentVersion).where(DocumentVersion.signature_request_id == request.id)
    )


def widget_context(ctx: Ctx, request: SignatureRequest, token_exp: int) -> dict:
    db = ctx.db
    document = db.get(Document, request.document_id)
    signer = db.get(Signer, request.signer_id)
    context = {
        "id": request.id,
        "status": request.status.value,
        "provider": request.provider.value,
        "document_name": flow.document_name(document),
        "signer_name": signer.full_name,
        "allowed_origins": allowed_origins(ctx.system),
        "agent_url": ctx.settings.agent_url,
        "token_expires_at": datetime.fromtimestamp(token_exp, UTC),
        "signed_at": request.signed_at,
        "certificate": None,
        "document": None,
    }
    if request.certificate_id is not None:
        cert = db.get(Certificate, request.certificate_id)
        context["certificate"] = {
            "subject": cert.subject,
            "issuer_subject": cert.issuer_subject,
            "serial_number": cert.serial_number,
        }
    version = _signed_version(ctx, request)
    if version is not None:
        context["document"] = flow.document_block(ctx, version, include_bytes=False)
    return context


def signed_pdf(ctx: Ctx, request: SignatureRequest) -> tuple[bytes, int]:
    version = _signed_version(ctx, request)
    if request.status != RequestStatus.SIGNED or version is None:
        raise Conflict("la solicitud todavía no está firmada")
    return ctx.storage.read(version.storage_ref), version.version_number


def load_request(ctx: Ctx, request_id: uuid.UUID) -> SignatureRequest:
    return flow._get_request(ctx, request_id)
