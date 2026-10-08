"""Operaciones de administración: historial, custodia, webhooks, anclas de confianza y certificado propio."""

import hashlib
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from asn1crypto import pem
from asn1crypto import x509 as ax509
from cryptography import x509 as cx509
from cryptography.hazmat.primitives import serialization
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import trust
from ..config import Settings
from ..errors import Conflict, NotFound, Unprocessable
from ..models import (
    AdminEvent,
    AuditEvent,
    Certificate,
    DeliveryStatus,
    Document,
    DocumentVersion,
    IntegratingSystem,
    Provider,
    RequestStatus,
    SignatureRequest,
    Signer,
    SigningChallenge,
    WebhookDelivery,
)
from ..providers import _local
from ..providers.local import CERT_FILE, KEY_FILE, LocalPAdESProvider, _lock

ACTOR = "admin"
FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
ARCHIVE_DIR = "archive"
MAX_LIMIT = 200


def record(db: Session, action: str, detail: dict, actor: str = ACTOR) -> None:
    """Registra la acción en la transacción en curso (el llamador confirma)."""
    db.add(AdminEvent(actor=actor, action=action, detail=detail))


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _page(limit: int, offset: int) -> tuple[int, int]:
    if not 1 <= limit <= MAX_LIMIT:
        raise Unprocessable(f"'limit' debe estar entre 1 y {MAX_LIMIT}")
    if offset < 0:
        raise Unprocessable("'offset' no puede ser negativo")
    return limit, offset


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# --- historial de solicitudes ----------------------------------------------------------------------


def list_requests(
    db: Session,
    *,
    integrating_system_id: uuid.UUID | None = None,
    status: RequestStatus | None = None,
    provider: Provider | None = None,
    signer: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    limit, offset = _page(limit, offset)
    filters = []
    if integrating_system_id:
        filters.append(SignatureRequest.integrating_system_id == integrating_system_id)
    if status:
        filters.append(SignatureRequest.status == status)
    if provider:
        filters.append(SignatureRequest.provider == provider)
    if signer:
        pattern = f"%{_like_escape(signer.lower())}%"
        filters.append(
            or_(Signer.identifier == signer, func.lower(Signer.full_name).like(pattern, escape="\\"))
        )
    if created_from:
        filters.append(SignatureRequest.created_at >= _aware(created_from))
    if created_to:
        filters.append(SignatureRequest.created_at <= _aware(created_to))

    def joined(stmt):
        return (
            stmt.select_from(SignatureRequest)
            .join(Document, Document.id == SignatureRequest.document_id)
            .join(IntegratingSystem, IntegratingSystem.id == SignatureRequest.integrating_system_id)
            .join(Signer, Signer.id == SignatureRequest.signer_id)
            .outerjoin(Certificate, Certificate.id == SignatureRequest.certificate_id)
            .outerjoin(DocumentVersion, DocumentVersion.id == Document.current_version_id)
            .where(*filters)
        )

    total = db.scalar(joined(select(func.count(SignatureRequest.id))))
    rows = db.execute(
        joined(select(SignatureRequest, Document, IntegratingSystem, Signer, Certificate, DocumentVersion))
        .order_by(SignatureRequest.created_at.desc(), SignatureRequest.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": r.id,
                "created_at": r.created_at,
                "signed_at": r.signed_at,
                "status": r.status.value,
                "provider": r.provider.value,
                "integrating_system": {"id": s.id, "name": s.name},
                "document": {
                    "id": d.id,
                    "external_document_id": d.external_document_id,
                    "signing_status": d.signing_status.value,
                    "current_version_number": v.version_number if v else None,
                },
                "signer": {"name": sg.full_name, "identifier": sg.identifier},
                "certificate": {"subject": c.subject, "serial_number": c.serial_number} if c else None,
            }
            for r, d, s, sg, c, v in rows
        ],
    }


# --- cadena de custodia ----------------------------------------------------------------------------


def custody(db: Session, document_id: uuid.UUID) -> dict:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFound("documento inexistente")
    versions = db.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version_number)
    ).all()
    requests = db.scalars(
        select(SignatureRequest)
        .where(SignatureRequest.document_id == document.id)
        .order_by(SignatureRequest.created_at, SignatureRequest.id)
    ).all()
    out_requests = []
    for r in requests:
        events = db.scalars(
            select(AuditEvent)
            .where(AuditEvent.signature_request_id == r.id)
            .order_by(AuditEvent.created_at)
        ).all()
        challenges = db.scalars(
            select(SigningChallenge)
            .where(SigningChallenge.signature_request_id == r.id)
            .order_by(SigningChallenge.created_at)
        ).all()
        deliveries = db.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.signature_request_id == r.id)
            .order_by(WebhookDelivery.created_at)
        ).all()
        out_requests.append(
            {
                "id": r.id,
                "status": r.status.value,
                "provider": r.provider.value,
                "created_at": r.created_at,
                "signed_at": r.signed_at,
                "batch_id": r.batch_id,
                "events": [
                    {"event_type": e.event_type, "payload": e.payload, "created_at": e.created_at}
                    for e in events
                ],
                "challenges": [  # sin el hash a firmar
                    {
                        "id": c.id,
                        "created_at": c.created_at,
                        "expires_at": c.expires_at,
                        "consumed_at": c.consumed_at,
                    }
                    for c in challenges
                ],
                "webhook_deliveries": [_delivery(d) for d in deliveries],  # sin el cuerpo
            }
        )
    return {
        "document": {
            "id": document.id,
            "external_document_id": document.external_document_id,
            "integrating_system_id": document.integrating_system_id,
            "signing_status": document.signing_status.value,
            "signature_deadline": document.signature_deadline,
            "current_version_id": document.current_version_id,
        },
        "versions": [
            {
                "id": v.id,
                "version_number": v.version_number,
                "origin": v.origin.value,
                "signature_level": v.signature_level.value if v.signature_level else None,
                "document_hash": v.document_hash,
                "signature_request_id": v.signature_request_id,
                "created_at": v.created_at,
                "is_current": v.id == document.current_version_id,
            }
            for v in versions
        ],
        "signature_requests": out_requests,
    }


# --- webhooks ---------------------------------------------------------------------------------------


def _delivery(d: WebhookDelivery) -> dict:
    return {
        "id": d.id,
        "signature_request_id": d.signature_request_id,
        "event_type": d.event_type,
        "url": d.url,
        "status": d.status.value,
        "attempts": d.attempts,
        "last_attempt_at": d.last_attempt_at,
        "next_attempt_at": d.next_attempt_at,
        "last_error": d.last_error,
        "response_status": d.response_status,
        "created_at": d.created_at,
    }


def list_deliveries(
    db: Session, *, status: DeliveryStatus | None = None, limit: int = 50, offset: int = 0
) -> dict:
    limit, offset = _page(limit, offset)
    where = [WebhookDelivery.status == status] if status else []
    total = db.scalar(select(func.count(WebhookDelivery.id)).where(*where))
    rows = db.scalars(
        select(WebhookDelivery)
        .where(*where)
        .order_by(WebhookDelivery.created_at.desc(), WebhookDelivery.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {"total": total, "limit": limit, "offset": offset, "items": [_delivery(d) for d in rows]}


def retry_delivery(db: Session, delivery_id: uuid.UUID) -> dict:
    delivery = db.get(WebhookDelivery, delivery_id)
    if delivery is None:
        raise NotFound("entrega inexistente")
    if delivery.status != DeliveryStatus.FAILED:
        raise Conflict("solo se pueden reenviar las entregas fallidas")
    record(
        db,
        "webhook_retry",
        {
            "delivery_id": str(delivery.id),
            "previous_attempts": delivery.attempts,
            "last_error": delivery.last_error,
        },
    )
    delivery.status = DeliveryStatus.PENDING
    delivery.attempts = 0
    delivery.last_error = None
    delivery.next_attempt_at = datetime.now(UTC)
    db.commit()
    return _delivery(delivery)


def list_events(db: Session, *, limit: int = 50, offset: int = 0) -> dict:
    limit, offset = _page(limit, offset)
    total = db.scalar(select(func.count(AdminEvent.id)))
    rows = db.scalars(
        select(AdminEvent).order_by(AdminEvent.created_at.desc(), AdminEvent.id).limit(limit).offset(offset)
    ).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {"id": e.id, "actor": e.actor, "action": e.action, "detail": e.detail, "created_at": e.created_at}
            for e in rows
        ],
    }


# --- anclas de confianza -----------------------------------------------------------------------------


def _trust_dir(settings: Settings) -> Path:
    return Path(settings.trust_dir)


def _fingerprint(cert: ax509.Certificate) -> str:
    return hashlib.sha256(cert.dump()).hexdigest()


def _anchor_files(settings: Settings) -> list[tuple[Path, list[ax509.Certificate]]]:
    directory = _trust_dir(settings)
    if not directory.is_dir():
        return []
    found = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() in trust.CERT_SUFFIXES:
            found.append((path, trust._load_file(path)))
    return found


def _describe(cert: ax509.Certificate, file_name: str) -> dict:
    return {
        "fingerprint": _fingerprint(cert),
        "subject": cert.subject.human_friendly,
        "issuer": cert.issuer.human_friendly,
        "not_before": cert["tbs_certificate"]["validity"]["not_before"].native,
        "not_after": cert["tbs_certificate"]["validity"]["not_after"].native,
        "is_root": cert.subject == cert.issuer,
        "file": file_name,
    }


def list_anchors(settings: Settings) -> list[dict]:
    return [_describe(c, path.name) for path, certs in _anchor_files(settings) for c in certs]


def add_anchor(db: Session, settings: Settings, certificate_pem: str) -> dict:
    data = certificate_pem.encode()
    if not pem.detect(data):
        raise Unprocessable("'certificate_pem' no es un certificado PEM")
    try:
        blocks = pem.unarmor(data, multiple=True)
        certs = [ax509.Certificate.load(der) for _t, _h, der in blocks]
    except (ValueError, TypeError) as e:
        raise Unprocessable("'certificate_pem' no es un certificado válido") from e
    if len(certs) != 1:
        raise Unprocessable("enviar un único certificado por ancla")
    cert = certs[0]
    now = datetime.now(UTC)
    validity = cert["tbs_certificate"]["validity"]
    if validity["not_after"].native <= now:
        raise Unprocessable("el certificado está vencido")
    if not (cert.ca or cert.subject == cert.issuer):
        raise Unprocessable("el certificado no es una autoridad (CA) ni está autofirmado")
    fingerprint = _fingerprint(cert)
    if any(a["fingerprint"] == fingerprint for a in list_anchors(settings)):
        raise Conflict("ya existe un ancla con esa huella")

    directory = _trust_dir(settings)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{fingerprint[:32]}.crt"
    with open(path, "xb") as f:  # nunca sobrescribe
        f.write(pem.armor("CERTIFICATE", cert.dump()))
    trust._cached.cache_clear()
    record(db, "trust_anchor_added", {"fingerprint": fingerprint, "subject": cert.subject.human_friendly})
    db.commit()
    return _describe(cert, path.name)


def remove_anchor(db: Session, settings: Settings, fingerprint: str) -> dict:
    if not FINGERPRINT.match(fingerprint):
        raise NotFound("ancla inexistente")
    for path, certs in _anchor_files(settings):
        for cert in certs:
            if _fingerprint(cert) == fingerprint:
                if len(certs) != 1:
                    raise Conflict("el archivo del ancla contiene otros certificados: quitarlo a mano")
                described = _describe(cert, path.name)
                path.unlink()
                trust._cached.cache_clear()
                record(
                    db, "trust_anchor_removed", {"fingerprint": fingerprint, "subject": described["subject"]}
                )
                db.commit()
                return described
    raise NotFound("ancla inexistente")


# --- certificado propio ------------------------------------------------------------------------------


def _local_describe(path: Path) -> dict:
    cert = cx509.load_pem_x509_certificate(path.read_bytes())
    der = cert.public_bytes(serialization.Encoding.DER)
    return {
        "subject": cert.subject.rfc4514_string(),
        "serial_number": str(cert.serial_number),
        "fingerprint": hashlib.sha256(der).hexdigest(),
        "not_before": cert.not_valid_before_utc,
        "not_after": cert.not_valid_after_utc,
        "file": path.name,
    }


def archived_local_certificates(settings: Settings) -> list[Path]:
    directory = Path(settings.local_cert_dir) / ARCHIVE_DIR
    return sorted(directory.glob("*.crt")) if directory.is_dir() else []


def local_certificate_info(settings: Settings) -> dict:
    current = Path(settings.local_cert_dir) / CERT_FILE
    return {
        "current": _local_describe(current) if current.is_file() else None,
        "archived": [_local_describe(p) for p in archived_local_certificates(settings)],
    }


def rotate_local_certificate(db: Session, settings: Settings) -> dict:
    directory = Path(settings.local_cert_dir)
    key_path, cert_path = directory / KEY_FILE, directory / CERT_FILE
    with _lock:
        archived = None
        if cert_path.is_file():
            old = _local_describe(cert_path)
            target = directory / ARCHIVE_DIR / f"demo-signer-{old['serial_number']}.crt"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(cert_path.read_bytes())  # solo la parte pública
            archived = old["fingerprint"]
        key_path.unlink(missing_ok=True)  # la clave vieja no debe quedar utilizable
        cert_path.unlink(missing_ok=True)
        LocalPAdESProvider(directory)._generate(key_path, cert_path)
    _local.cache_clear()
    new = _local_describe(cert_path)
    record(
        db,
        "local_certificate_rotated",
        {"archived_fingerprint": archived, "new_fingerprint": new["fingerprint"]},
    )
    db.commit()
    return {"current": new, "archived_fingerprint": archived}
