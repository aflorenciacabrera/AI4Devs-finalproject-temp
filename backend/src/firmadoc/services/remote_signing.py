"""Firma remota (`firmar`): envío del documento y procesamiento del callback del servicio.

El servicio firma con una clave que Firmadoc nunca ve, así que lo que devuelve se **valida** antes de
aceptarse: contenido original intacto, una firma nueva, cadena de confianza y CUIL del firmante.
"""

import base64
import binascii
import io
import json
from datetime import UTC, datetime, timedelta

from asn1crypto import x509 as ax509
from pyhanko.pdf_utils.reader import PdfFileReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import webhooks
from ..certificate_validation import extract_cuil, normalize_cuil
from ..config import Settings
from ..errors import Conflict, NotFound, Unauthorized, Unprocessable
from ..models import (
    AuditEvent,
    Certificate,
    Document,
    IntegratingSystem,
    Provider,
    RequestStatus,
    RevocationStatus,
    SignatureRequest,
    Signer,
)
from ..pdf_engine import PdfEngineError, signature_count, validate_pdf, verify_pdf
from ..providers import firmar
from ..storage import DocumentStorage, StorageError
from . import signature_flow as flow
from .documents import verification_anchors
from .signature_flow import Ctx

CALLBACK_PATH = "/api/v1/providers/firmar/callback"
STATUSES = {"signed", "rejected", "expired"}


def _audit(db: Session, request: SignatureRequest, event_type: str, payload: dict) -> None:
    db.add(AuditEvent(signature_request_id=request.id, event_type=event_type, payload=payload))


def prepare(ctx: Ctx, request: SignatureRequest) -> dict:
    """Envía la versión vigente al servicio y deja la solicitud esperando su callback."""
    db = ctx.db
    document = db.get(Document, request.document_id)
    current = flow._latest_version(db, document)
    try:
        pdf = ctx.storage.read(current.storage_ref)
    except StorageError as e:
        raise Conflict("no se pudo leer el documento") from e
    signer = db.get(Signer, request.signer_id)

    callback_url = ctx.settings.public_base_url.rstrip("/") + CALLBACK_PATH
    operation = firmar.FirmarClient(ctx.settings).submit(pdf, normalize_cuil(signer.identifier), callback_url)

    request.remote_operation_id = operation.operation_id
    request.status = RequestStatus.SIGNING
    _audit(db, request, "prepared", {"remote_operation_id": operation.operation_id})
    db.commit()
    return {
        "challenges": [],
        "expires_at": datetime.now(UTC) + timedelta(seconds=ctx.settings.challenge_ttl_seconds),
        "remote": {
            "operation_id": operation.operation_id,
            "authorization_url": operation.authorization_url,
        },
    }


def _fail_remote(ctx: Ctx, request: SignatureRequest, reason: str, code: str | None) -> Unprocessable:
    """Marca la solicitud `failed`, la notifica y devuelve el error a responder."""
    request.status = RequestStatus.FAILED
    _audit(ctx.db, request, "failed", {"reason": reason, "code": code})
    webhooks.enqueue(ctx, request, webhooks.EVENT_FAILED, error_code=code)
    ctx.db.commit()
    return Unprocessable(reason, code=code)


def _register_certificate(db: Session, request: SignatureRequest, cert: ax509.Certificate) -> Certificate:
    serial = str(cert.serial_number)
    record = db.scalar(select(Certificate).where(Certificate.serial_number == serial))
    if record is None:
        validity = cert["tbs_certificate"]["validity"]
        record = Certificate(
            signer_id=request.signer_id,
            subject=cert.subject.human_friendly,
            issuer_subject=cert.issuer.human_friendly,
            cuil=extract_cuil(cert),
            serial_number=serial,
            provider=Provider.FIRMAR,
            revocation_status=RevocationStatus.UNKNOWN,
            issued_at=validity["not_before"].native,
            expires_at=validity["not_after"].native,
        )
        db.add(record)
        db.flush()
    return record


def _accept_signed(ctx: Ctx, request: SignatureRequest, signed: bytes) -> None:
    """Valida el PDF devuelto y crea la versión firmada. Ante cualquier falla, la solicitud pasa a `failed`."""
    db = ctx.db
    document = db.get(Document, request.document_id)
    current = flow._latest_version(db, document)
    try:
        original = ctx.storage.read(current.storage_ref)
    except StorageError as e:
        raise Conflict("no se pudo leer el documento") from e

    def reject(reason: str, code: str | None = "remote_invalid_document") -> None:
        raise _fail_remote(ctx, request, reason, code)

    if len(signed) > ctx.settings.max_document_bytes:
        reject("el documento devuelto excede el tamaño máximo permitido")
    try:
        validate_pdf(signed)
    except PdfEngineError:
        reject("el documento devuelto no es un PDF válido")
    if len(signed) <= len(original) or not signed.startswith(original):
        reject("el documento devuelto no conserva el contenido enviado")
    if signature_count(signed) != signature_count(original) + 1:
        reject("el documento devuelto no agrega exactamente una firma")

    roots, others = verification_anchors(ctx)
    try:
        checks = verify_pdf(signed, roots, others)
    except Exception:  # noqa: BLE001 - un PDF dañado no debe producir un 500
        reject("no se pudieron leer las firmas del documento devuelto")
    last = checks[-1]
    if not last.ok:
        reject("la firma devuelta no es válida o su cadena no llega a una ancla de confianza", "certificate_untrusted")

    cert = PdfFileReader(io.BytesIO(signed)).embedded_signatures[-1].signer_cert
    signer = db.get(Signer, request.signer_id)
    cuil = extract_cuil(cert)
    if cuil is None or normalize_cuil(cuil) != normalize_cuil(signer.identifier):
        reject("el CUIL del certificado no coincide con el del firmante", "cuil_mismatch")

    record = _register_certificate(db, request, cert)
    request.certificate_id = record.id
    stamp = {"status": "embedded"} if last.timestamp_present else {"status": "absent"}
    flow._register_signed(ctx, request, signed, stamp, datetime.now(UTC))


def handle_callback(
    db: Session,
    storage: DocumentStorage,
    settings: Settings,
    raw_body: bytes,
    signature_header: str | None,
) -> dict:
    if not settings.firmar_base_url or not settings.firmar_callback_secret:
        raise NotFound("no encontrado")
    if not firmar.verify_callback_signature(settings.firmar_callback_secret, raw_body, signature_header):
        raise Unauthorized("firma del callback inválida")
    try:
        data = json.loads(raw_body)
        operation_id = str(data["operation_id"])
        status = data["status"]
    except (ValueError, KeyError, TypeError):
        raise Unprocessable("cuerpo del callback inválido", code="invalid_callback") from None
    if status not in STATUSES:
        raise Unprocessable("estado del callback inválido", code="invalid_callback")

    request = db.scalar(select(SignatureRequest).where(SignatureRequest.remote_operation_id == operation_id))
    if request is None:
        raise NotFound("operación inexistente")
    if request.status in (RequestStatus.SIGNED, RequestStatus.FAILED):
        return {"status": "already_processed"}
    if request.status != RequestStatus.SIGNING:
        raise Conflict(f"la solicitud está en estado '{request.status.value}'")

    system = db.get(IntegratingSystem, request.integrating_system_id)
    ctx = Ctx(db=db, storage=storage, settings=settings, system=system)

    if status != "signed":
        _fail_remote(ctx, request, f"el servicio de firma remota informó '{status}'", f"remote_{status}")
        return {"status": "recorded"}  # el servicio no necesita un error: el resultado ya se registró

    encoded = data.get("signed_document_base64")
    if not isinstance(encoded, str) or not encoded:
        raise Unprocessable("falta 'signed_document_base64'", code="invalid_callback")
    try:
        signed = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise Unprocessable("'signed_document_base64' no es base64 válido", code="invalid_callback") from None
    _accept_signed(ctx, request, signed)
    return {"status": "signed", "signature_request_id": str(request.id)}
