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
    SignatureBatch,
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


def _origin(request: SignatureRequest) -> dict:
    if request.batch_id is None:
        return {"kind": "individual"}
    return {"kind": "batch", "batch_id": request.batch_id, "label": "#" + str(request.batch_id)[:8]}


# --- historial de solicitudes ----------------------------------------------------------------------


def list_requests(
    db: Session,
    *,
    integrating_system_id: uuid.UUID | None = None,
    status: RequestStatus | None = None,
    provider: Provider | None = None,
    signer: str | None = None,
    origin: str | None = None,
    q: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    limit, offset = _page(limit, offset)
    if origin not in (None, "individual", "batch"):
        raise Unprocessable("'origin' debe ser 'individual' o 'batch'")
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
    if origin == "batch":
        filters.append(SignatureRequest.batch_id.is_not(None))
    elif origin == "individual":
        filters.append(SignatureRequest.batch_id.is_(None))
    if q:
        pattern = f"%{_like_escape(q.lower())}%"
        filters.append(
            or_(
                func.lower(Document.external_document_id).like(pattern, escape="\\"),
                Signer.identifier == q,
                func.lower(Signer.full_name).like(pattern, escape="\\"),
            )
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
            .outerjoin(SignatureBatch, SignatureBatch.id == SignatureRequest.batch_id)
            .where(*filters)
        )

    total = db.scalar(joined(select(func.count(SignatureRequest.id))))
    rows = db.execute(
        joined(
            select(SignatureRequest, Document, IntegratingSystem, Signer, Certificate, DocumentVersion, SignatureBatch)
        )
        # Las solicitudes de un lote van juntas: se agrupan por la fecha del lote.
        .order_by(
            func.coalesce(SignatureBatch.created_at, SignatureRequest.created_at).desc(),
            SignatureRequest.batch_id,
            SignatureRequest.created_at.desc(),
            SignatureRequest.id,
        )
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
                    "signature_deadline": d.signature_deadline,
                    "current_version_number": v.version_number if v else None,
                },
                "origin": _origin(r),
                "signer": {"name": sg.full_name, "identifier": sg.identifier},
                "certificate": {"subject": c.subject, "serial_number": c.serial_number} if c else None,
            }
            for r, d, s, sg, c, v, _batch in rows
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
    system = db.get(IntegratingSystem, document.integrating_system_id)
    return {
        "document": {
            "id": document.id,
            "external_document_id": document.external_document_id,
            "integrating_system_id": document.integrating_system_id,
            "integrating_system_name": system.name if system else None,
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
        "timeline": _timeline(db, system, requests, out_requests),
        "technical": _technical(db, document, versions, requests),
    }


# --- línea de tiempo y detalle técnico --------------------------------------------------------------

ENGINE = "Motor Firmadoc"
AGENT = "Firmadoc Agent"
PROVIDER_LABELS = {"token": "Token (firma digital)", "local": "Firma propia (demostración)", "firmar": "Firma remota"}


def _event_entry(event: dict, request: dict, system_name: str, signer_name: str) -> list[dict]:
    """Entradas de la línea de tiempo para un evento de auditoría (puede ser más de una)."""
    kind, payload, at = event["event_type"], event["payload"] or {}, event["created_at"]

    def entry(title: str, actor: str, detail: str, k: str = "info") -> dict:
        return {"at": at, "actor": actor, "title": title, "detail": detail, "kind": k}

    if kind == "created":
        provider = PROVIDER_LABELS.get(payload.get("provider", ""), payload.get("provider", ""))
        return [entry("Solicitud creada por el sistema integrador", system_name, f"Método inicial: {provider}")]
    if kind == "provider_selected":
        new = PROVIDER_LABELS.get(payload.get("to", ""), payload.get("to", ""))
        return [entry("Método de firma elegido", signer_name, f"Se eligió: {new}")]
    if kind == "prepared":
        return [
            entry(
                "Desafío preparado: hash SHA-256 a firmar",
                ENGINE,
                "De un solo uso, vence a los pocos minutos y queda atado a la sesión",
            )
        ]
    if kind == "rejected":
        return [entry("Certificado rechazado", ENGINE, payload.get("reason") or payload.get("code") or "", "error")]
    if kind == "signed":
        out = []
        if request["provider"] == "token":
            out.append(entry("Firma recibida del agente local", AGENT, "El PIN se ingresó en la PC del firmante; no llega al servidor"))
        level = payload.get("signature_level") or ""
        out.append(entry("Firma PAdES incrustada en el documento", ENGINE, f"Nivel {level}".strip()))
        out.append(
            entry(
                f"Nueva versión registrada: v{payload.get('version_number')}, vigente",
                ENGINE,
                "Las versiones anteriores se conservan sin cambios",
                "ok",
            )
        )
        return out
    if kind == "failed":
        return [entry("La firma falló", ENGINE, payload.get("reason") or payload.get("code") or "", "error")]
    if kind == "timestamp_unavailable":
        return [entry("Sello de tiempo no disponible", ENGINE, payload.get("reason") or "", "warning")]
    return [entry(kind, ENGINE, "")]


def _delivery_entry(d: dict, system_name: str) -> dict:
    ok = d["status"] == "delivered"
    failed = d["status"] == "failed"
    title = (
        "Webhook entregado al sistema integrador"
        if ok
        else "Webhook fallido" if failed else "Webhook pendiente de entrega"
    )
    detail = f"Intento {d['attempts']}"
    if d.get("response_status"):
        detail += f" · respuesta {d['response_status']}"
    return {
        "at": d["last_attempt_at"] or d["created_at"],
        "actor": ENGINE,
        "title": title,
        "detail": detail,
        "kind": "ok" if ok else "error" if failed else "warning",
    }


def _timeline(db: Session, system, requests: list[SignatureRequest], out_requests: list[dict]) -> list[dict]:
    system_name = system.name if system else "Sistema integrador"
    entries: list[tuple[datetime, int, dict]] = []
    order = 0
    for r, out in zip(requests, out_requests, strict=True):
        signer = db.get(Signer, r.signer_id)
        signer_name = signer.full_name if signer else "Firmante"
        for event in out["events"]:
            if event["event_type"].startswith("batch_"):
                continue
            for item in _event_entry(event, out, system_name, signer_name):
                order += 1
                entries.append((_aware(item["at"]), order, {**item, "signature_request_id": r.id}))
        for d in out["webhook_deliveries"]:
            item = _delivery_entry(d, system_name)
            order += 1
            entries.append((_aware(item["at"]), order, {**item, "signature_request_id": r.id}))
    entries.sort(key=lambda t: (t[0], t[1]))
    return [e for _, _, e in entries]


def _technical(
    db: Session, document: Document, versions: list[DocumentVersion], requests: list[SignatureRequest]
) -> dict | None:
    """Datos técnicos de la última firma completada. Sin IP de origen: el sistema no la registra."""
    signed = [r for r in requests if r.status == RequestStatus.SIGNED]
    if not signed:
        return None
    request = max(signed, key=lambda r: _aware(r.signed_at) or datetime.min.replace(tzinfo=UTC))
    version = next((v for v in versions if v.signature_request_id == request.id), None)
    certificate = db.get(Certificate, request.certificate_id) if request.certificate_id else None
    signer = db.get(Signer, request.signer_id)
    original = min(versions, key=lambda v: v.version_number) if versions else None
    return {
        "transaction_id": request.id,
        "provider": request.provider.value,
        "signature_level": version.signature_level.value if version and version.signature_level else None,
        "certificate": (
            {
                "subject": certificate.subject,
                "issuer_subject": certificate.issuer_subject,
                "serial_number": certificate.serial_number,
            }
            if certificate
            else None
        ),
        "signer": {"name": signer.full_name, "identifier": signer.identifier} if signer else None,
        "original_hash": original.document_hash if original else None,
        "signed_hash": version.document_hash if version else None,
        "signed_version_number": version.version_number if version else None,
    }


def version_download(db: Session, storage, document_id: uuid.UUID, number: int) -> tuple[bytes, str]:
    """El PDF de una versión (lectura de administración). Devuelve los bytes y un nombre de archivo."""
    document = db.get(Document, document_id)
    version = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id, DocumentVersion.version_number == number
        )
    )
    if document is None or version is None:
        raise NotFound("versión inexistente")
    from ..filenames import download_name

    # Todas las versiones se descargan con el nombre original del archivo (FIRDOC-53).
    return storage.read(version.storage_ref), download_name(document.external_document_id, document.id)


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
