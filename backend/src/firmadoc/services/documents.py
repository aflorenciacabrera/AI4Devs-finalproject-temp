"""Estado, firmantes y verificación de un documento."""

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from asn1crypto import pem
from asn1crypto import x509 as ax509
from sqlalchemy import select

from ..errors import Conflict, NotFound, Unprocessable
from ..models import (
    Certificate,
    Document,
    DocumentVersion,
    SignatureRequest,
    Signer,
    SigningStatus,
    VersionOrigin,
)
from ..pdf_engine import verify_pdf
from ..providers.local import CERT_FILE
from ..storage import StorageError
from ..trust import load_trust_store
from .signature_flow import Ctx, _aware

SETTABLE = {SigningStatus.DRAFT, SigningStatus.PENDING_SIGNATURE}


def _get_document(ctx: Ctx, document_id: uuid.UUID) -> Document:
    document = ctx.db.scalar(
        select(Document).where(
            Document.id == document_id, Document.integrating_system_id == ctx.system.id
        )
    )
    if document is None:
        raise NotFound("documento inexistente")
    return document


def _current_version(ctx: Ctx, document: Document) -> DocumentVersion | None:
    if document.current_version_id is None:
        return None
    return ctx.db.get(DocumentVersion, document.current_version_id)


def _out(ctx: Ctx, document: Document) -> dict:
    version = _current_version(ctx, document)
    deadline = document.signature_deadline
    base = ctx.settings.public_base_url.rstrip("/")
    return {
        "id": document.id,
        "external_document_id": document.external_document_id,
        "signing_status": document.signing_status.value,
        "signature_deadline": deadline,
        "deadline_passed": bool(deadline and _aware(deadline) <= datetime.now(UTC)),
        "current_version_number": version.version_number if version else None,
        "download_url": (
            f"{base}/api/v1/documents/{document.id}/versions/{version.version_number}/download"
            if version
            else None
        ),
    }


def get_document(ctx: Ctx, document_id: uuid.UUID) -> dict:
    return _out(ctx, _get_document(ctx, document_id))


def update_document(ctx: Ctx, document_id: uuid.UUID, fields: dict) -> dict:
    """`fields` trae solo lo enviado: `signing_status` y/o `signature_deadline` (puede ser None)."""
    if not fields:
        raise Unprocessable("enviar 'signing_status' o 'signature_deadline'")
    document = _get_document(ctx, document_id)

    if "signing_status" in fields:
        target = fields["signing_status"]
        if target not in SETTABLE:
            raise Unprocessable("'signing_status' solo admite 'draft' o 'pending_signature'")
        if document.signing_status == SigningStatus.SIGNED and target == SigningStatus.DRAFT:
            raise Conflict("un documento firmado no puede volver a borrador")
    if fields.get("signature_deadline") is not None:
        deadline = fields["signature_deadline"]
        if deadline.tzinfo is None:
            raise Unprocessable("'signature_deadline' debe incluir zona horaria")
        if deadline <= datetime.now(UTC):
            raise Unprocessable("'signature_deadline' debe ser una fecha futura")

    if "signing_status" in fields:
        document.signing_status = fields["signing_status"]
    if "signature_deadline" in fields:
        document.signature_deadline = fields["signature_deadline"]
    ctx.db.commit()
    return _out(ctx, document)


def list_signatures(ctx: Ctx, document_id: uuid.UUID) -> list[dict]:
    document = _get_document(ctx, document_id)
    rows = ctx.db.execute(
        select(DocumentVersion, SignatureRequest, Signer, Certificate)
        .join(SignatureRequest, SignatureRequest.id == DocumentVersion.signature_request_id)
        .join(Signer, Signer.id == SignatureRequest.signer_id)
        .outerjoin(Certificate, Certificate.id == SignatureRequest.certificate_id)
        .where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.origin == VersionOrigin.SIGNED,
        )
        .order_by(DocumentVersion.version_number)
    ).all()
    return [
        {
            "version_number": version.version_number,
            "signer_name": signer.full_name,
            "signer_identifier": signer.identifier,
            "signed_at": request.signed_at,
            "provider": request.provider.value,
            "certificate": (
                {
                    "subject": cert.subject,
                    "issuer_subject": cert.issuer_subject,
                    "serial_number": cert.serial_number,
                }
                if cert
                else None
            ),
        }
        for version, request, signer, cert in rows
    ]


def verification_anchors(ctx: Ctx) -> tuple[list[ax509.Certificate], list[ax509.Certificate]]:
    """Raíces e intermedias configuradas, más el certificado autofirmado del proveedor `local`."""
    store = load_trust_store(ctx.settings.trust_dir)
    roots, others = list(store.roots), list(store.intermediates)
    local = Path(ctx.settings.local_cert_dir) / CERT_FILE
    if local.is_file():
        data = local.read_bytes()
        roots.append(ax509.Certificate.load(pem.unarmor(data)[2] if pem.detect(data) else data))
    archive = local.parent / "archive"  # certificados propios de rotaciones anteriores (solo la parte pública)
    if archive.is_dir():
        for path in sorted(archive.glob("*.crt")):
            roots.append(ax509.Certificate.load(pem.unarmor(path.read_bytes())[2]))
    return roots, others


def verify_document(ctx: Ctx, document_id: uuid.UUID) -> dict:
    document = _get_document(ctx, document_id)
    version = _current_version(ctx, document)
    if version is None:
        raise Conflict("el documento no tiene versiones")
    try:
        pdf = ctx.storage.read(version.storage_ref)
    except StorageError as e:
        raise Conflict("el binario de la versión vigente no está disponible") from e

    hash_matches = hashlib.sha256(pdf).hexdigest() == version.document_hash
    roots, others = verification_anchors(ctx)
    try:
        checks = verify_pdf(pdf, roots, others)
    except Exception as e:
        raise Unprocessable(f"no se pudieron leer las firmas del PDF: {e}") from e
    signatures = [
        {
            "field_name": c.field_name,
            "signer_subject": c.signer_subject,
            "serial_number": c.serial_number,
            "claimed_signing_time": c.claimed_signing_time,
            "intact": c.intact,
            "valid": c.valid,
            "trusted": c.trusted,
            "modification_level": c.modification_level,
            "ok": c.ok,
            "timestamp": {
                "present": c.timestamp_present,
                "time": c.timestamp_time,
                "intact": c.timestamp_intact,
                "valid": c.timestamp_valid,
                "trusted": c.timestamp_trusted,
            },
        }
        for c in checks
    ]
    return {
        "document_id": document.id,
        "version_number": version.version_number,
        "hash_matches": hash_matches,
        "signatures": signatures,
        "valid": bool(hash_matches and signatures and all(c.ok for c in checks)),
        "checked_at": datetime.now(UTC),
    }
