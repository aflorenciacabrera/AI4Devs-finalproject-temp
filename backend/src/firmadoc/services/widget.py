"""Vista de una solicitud para el widget: solo lo necesario para dibujar la interfaz."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from ..errors import Conflict, Unprocessable
from ..models import (
    AuditEvent,
    Certificate,
    Document,
    DocumentVersion,
    IntegratingSystem,
    Provider,
    RequestStatus,
    SignatureRequest,
    Signer,
)
from ..providers import get_provider
from . import signature_flow as flow
from .signature_flow import Ctx


def allowed_origins(system: IntegratingSystem) -> list[str]:
    return [o.strip() for o in (system.allowed_origins or "").split(",") if o.strip()]


def available_providers(ctx: Ctx, request: SignatureRequest) -> list[Provider]:
    """Métodos que la persona puede elegir: los permitidos de la solicitud que estén habilitados."""
    configured = [p for p in (request.allowed_providers or "").split(",") if p]
    candidates = [Provider(p) for p in configured] or [request.provider]
    enabled = []
    for provider in candidates:
        try:
            get_provider(provider, ctx.settings)
        except Unprocessable:
            if provider == request.provider:  # el activo se informa siempre
                enabled.append(provider)
            continue
        enabled.append(provider)
    return enabled


def select_provider(ctx: Ctx, request: SignatureRequest, provider: Provider) -> None:
    if request.status != RequestStatus.PENDING:
        raise Conflict(f"la solicitud está en estado '{request.status.value}': no se puede cambiar el método")
    if provider not in available_providers(ctx, request):
        raise Unprocessable("ese método de firma no está disponible para esta solicitud", code="provider_not_allowed")
    if provider == request.provider:
        return
    previous = request.provider
    request.provider = provider
    ctx.db.add(
        AuditEvent(
            signature_request_id=request.id,
            event_type="provider_selected",
            payload={"from": previous.value, "to": provider.value},
        )
    )
    ctx.db.commit()


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
        "allowed_providers": [p.value for p in available_providers(ctx, request)],
        "token_expires_at": datetime.fromtimestamp(token_exp, UTC),
        "signed_at": request.signed_at,
        "certificate": None,
        "document": None,
        "signing_status": document.signing_status.value,
        "signature_deadline": document.signature_deadline,
    }
    context["page_count"], context["size_bytes"] = flow.document_stats(ctx, document)
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
