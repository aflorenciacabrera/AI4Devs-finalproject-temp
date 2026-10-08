"""Casos de uso del flujo de firma diferida: create / prepare / complete."""

import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from asn1crypto import x509 as ax509
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import signing_token, timestamping, webhooks
from ..config import Settings
from ..errors import Conflict, DomainError, NotFound, ServiceUnavailable, Unprocessable
from ..models import (
    AuditEvent,
    Certificate,
    Document,
    DocumentVersion,
    IntegratingSystem,
    Provider,
    RequestStatus,
    SignatureLevel,
    SignatureRequest,
    Signer,
    SigningChallenge,
    SigningStatus,
    VersionOrigin,
)
from ..pdf_engine import (
    PdfEngineError,
    TimestampUnavailable,
    finish_pdf,
    prepare_pdf,
    validate_pdf,
    verify_hash_signature,
)
from ..providers import get_provider
from ..storage import DocumentStorage, StorageError, sha256_hex


@dataclass
class Ctx:
    db: Session
    storage: DocumentStorage
    settings: Settings
    system: IntegratingSystem


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _audit(db: Session, request: SignatureRequest, event_type: str, payload: dict | None = None):
    db.add(AuditEvent(signature_request_id=request.id, event_type=event_type, payload=payload or {}))


def _get_request(ctx: Ctx, request_id: uuid.UUID) -> SignatureRequest:
    request = ctx.db.scalar(
        select(SignatureRequest).where(
            SignatureRequest.id == request_id,
            SignatureRequest.integrating_system_id == ctx.system.id,
        )
    )
    if request is None:
        raise NotFound("solicitud de firma inexistente")
    return request


def _latest_version(db: Session, document: Document) -> DocumentVersion:
    version = db.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )
    if version is None:
        raise Conflict("el documento no tiene versiones")
    return version


def _blob_ref(document_id: uuid.UUID, number: int, version_id: uuid.UUID) -> str:
    # El id de la versión evita colisiones con un binario huérfano de una transacción fallida.
    return f"documents/{document_id}/v{number}-{version_id}.pdf"


def document_name(document: Document) -> str:
    base = document.external_document_id or str(document.id)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in base)
    return f"{safe}.pdf"


def get_or_create_signer(db: Session, name: str, identifier: str, email: str) -> Signer:
    signer = db.scalar(select(Signer).where(Signer.identifier == identifier, Signer.email == email))
    if signer is None:
        signer = Signer(full_name=name, identifier=identifier, email=email)
        db.add(signer)
        db.flush()
    return signer


def create_request(
    ctx: Ctx,
    *,
    document_base64: str | None,
    document_id: uuid.UUID | None,
    external_document_id: str | None,
    signer_name: str,
    signer_identifier: str,
    signer_email: str,
    provider: Provider,
    callback_url: str | None = None,
    batch_id: uuid.UUID | None = None,
    commit: bool = True,
) -> SignatureRequest:
    get_provider(provider, ctx.settings)  # 422 si no está habilitado
    if callback_url is not None:
        webhooks.validate_callback_url(callback_url, ctx.settings)  # antes de crear nada
    db = ctx.db

    if (document_id is None) == (document_base64 is None):
        raise Unprocessable("enviar exactamente uno de 'document_id' o 'document_base64'")

    if document_id is not None:
        document = db.scalar(
            select(Document).where(
                Document.id == document_id, Document.integrating_system_id == ctx.system.id
            )
        )
        if document is None:
            raise NotFound("documento inexistente")
    else:
        try:
            data = base64.b64decode(document_base64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise Unprocessable("'document_base64' no es base64 válido") from e
        if len(data) > ctx.settings.max_document_bytes:
            raise Unprocessable("el documento excede el tamaño máximo permitido")
        try:
            validate_pdf(data)
        except PdfEngineError as e:
            raise Unprocessable(str(e)) from e
        document = Document(
            integrating_system_id=ctx.system.id, external_document_id=external_document_id
        )
        db.add(document)
        db.flush()
        version = DocumentVersion(
            id=uuid.uuid4(),
            document_id=document.id,
            version_number=1,
            origin=VersionOrigin.UPLOADED,
            storage_ref="",
            document_hash=sha256_hex(data),
        )
        version.storage_ref = _blob_ref(document.id, 1, version.id)
        ctx.storage.save(version.storage_ref, data)
        db.add(version)
        db.flush()
        document.current_version_id = version.id

    signer = get_or_create_signer(db, signer_name, signer_identifier, signer_email)

    request = SignatureRequest(
        document_id=document.id,
        integrating_system_id=ctx.system.id,
        signer_id=signer.id,
        provider=provider,
        callback_url=callback_url,
        batch_id=batch_id,
    )
    db.add(request)
    db.flush()
    _audit(db, request, "created", {"provider": provider.value})
    if commit:
        db.commit()
    return request


def signing_url(ctx: Ctx, request: SignatureRequest) -> str:
    """URL del widget. El token va en el fragmento: el navegador no lo envía al servidor."""
    settings = ctx.settings
    token = signing_token.issue(
        signing_token.secret_for(settings), request.id, settings.signing_token_ttl_seconds
    )
    return f"{settings.public_base_url.rstrip('/')}/sign/{request.id}#t={token}"


def prepare(
    ctx: Ctx, request_id: uuid.UUID, certificate_pem: str | None, session_ref: str
) -> dict:
    db = ctx.db
    request = _get_request(ctx, request_id)
    if request.status not in (RequestStatus.PENDING, RequestStatus.SIGNING):
        raise Conflict(f"la solicitud está en estado '{request.status.value}'")
    if request.provider == Provider.FIRMAR:
        from . import remote_signing  # evita el import circular

        return remote_signing.prepare(ctx, request)

    provider = get_provider(request.provider, ctx.settings)
    document = db.get(Document, request.document_id)
    signer = db.get(Signer, request.signer_id)
    current = _latest_version(db, document)
    try:
        pdf = ctx.storage.read(current.storage_ref)
    except StorageError as e:
        raise Conflict("no se pudo leer el documento") from e

    try:
        resolved = provider.resolve_certificate(db, certificate_pem, signer)
    except DomainError as e:
        # Rechazo no destructivo: la solicitud no cambia de estado, pero queda constancia.
        _audit(db, request, "rejected", {"code": e.code, "reason": e.detail})
        db.commit()
        raise
    reason = f"Firmado por {signer.full_name} (CUIL {signer.identifier}) vía Firmadoc"
    try:
        prepared = prepare_pdf(pdf, ax509.Certificate.load(resolved.der), reason)
    except Exception as e:  # pyHanko levanta tipos variados ante PDFs problemáticos
        raise Unprocessable(f"no se pudo preparar la firma del PDF: {e}") from e

    challenge_id = uuid.uuid4()
    expires_at = _now() + timedelta(seconds=ctx.settings.challenge_ttl_seconds)
    state = dict(prepared.state, cert_der=base64.b64encode(resolved.der).decode())
    ctx.storage.save(f"prepared/{challenge_id}/doc.pdf", prepared.pdf)
    ctx.storage.save(f"prepared/{challenge_id}/state.json", json.dumps(state).encode())

    hash_b64 = base64.b64encode(prepared.hash_to_sign).decode()
    db.add(
        SigningChallenge(
            id=challenge_id,
            signature_request_id=request.id,
            certificate_id=resolved.record.id,
            hash_to_sign=hash_b64,
            hash_algorithm="SHA-256",
            session_ref=session_ref,
            expires_at=expires_at,
        )
    )
    request.certificate_id = resolved.record.id
    request.status = RequestStatus.SIGNING
    _audit(db, request, "prepared", {"challenge_id": str(challenge_id)})
    db.commit()
    return {
        "challenges": [
            {
                "challenge_id": challenge_id,
                "document_name": document_name(document),
                "hash_algorithm": "SHA-256",
                "hash_to_sign": hash_b64,
            }
        ],
        "expires_at": expires_at,
    }


def _fail(ctx: Ctx, request: SignatureRequest, reason: str, code: str | None = None) -> None:
    request.status = RequestStatus.FAILED
    _audit(ctx.db, request, "failed", {"reason": reason, "code": code})
    webhooks.enqueue(ctx, request, webhooks.EVENT_FAILED, error_code=code)
    ctx.db.commit()
    raise Unprocessable(reason, code=code)


def _register_signed(
    ctx: Ctx, request: SignatureRequest, signed_pdf: bytes, stamp: dict, now: datetime
) -> DocumentVersion:
    """Crea la `DocumentVersion` firmada y deja la solicitud `signed` (auditoría y webhook incluidos).

    Es común a todos los proveedores: la firma por hash (`complete`) y la remota (callback).
    """
    db = ctx.db
    document = db.get(Document, request.document_id)
    number = (
        db.scalar(
            select(func.max(DocumentVersion.version_number)).where(
                DocumentVersion.document_id == document.id
            )
        )
        + 1
    )
    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=document.id,
        version_number=number,
        origin=VersionOrigin.SIGNED,
        signature_request_id=request.id,
        signature_level=SignatureLevel.B_T if stamp["status"] == "embedded" else SignatureLevel.B_B,
        storage_ref="",
        document_hash=sha256_hex(signed_pdf),
    )
    version.storage_ref = _blob_ref(document.id, number, version.id)
    ctx.storage.save(version.storage_ref, signed_pdf)
    try:
        db.add(version)
        db.flush()
        document.current_version_id = version.id
        document.signing_status = SigningStatus.SIGNED
        request.status = RequestStatus.SIGNED
        request.signed_at = now
        _audit(
            db,
            request,
            "signed",
            {"version_number": number, "signature_level": version.signature_level.value, "timestamp": stamp},
        )
        if stamp["status"] == "unavailable":
            _audit(db, request, "timestamp_unavailable", {"reason": stamp["reason"]})
        webhooks.enqueue(ctx, request, webhooks.EVENT_SIGNED)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise Conflict("otra firma se completó al mismo tiempo sobre el documento") from e
    return version


def complete(
    ctx: Ctx,
    request_id: uuid.UUID,
    signatures: list[tuple[uuid.UUID, str]],
    session_ref: str,
    include_bytes: bool = True,
) -> dict:
    db = ctx.db
    request = _get_request(ctx, request_id)
    if request.status != RequestStatus.SIGNING:
        raise Conflict(f"la solicitud está en estado '{request.status.value}': no está preparada")
    if request.provider == Provider.FIRMAR:
        raise Conflict(
            "la firma remota se completa por el callback del servicio", code="remote_signature_pending"
        )
    if len(signatures) > 1:
        raise Unprocessable("una solicitud admite una sola firma; para varias usar un lote")

    if signatures:
        challenge_id, signature_b64 = signatures[0]
        challenge = db.scalar(
            select(SigningChallenge).where(
                SigningChallenge.id == challenge_id,
                SigningChallenge.signature_request_id == request.id,
            )
        )
        if challenge is None:
            raise Conflict("el desafío no pertenece a esta solicitud")
        try:
            supplied: bytes | None = base64.b64decode(signature_b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise Unprocessable("'signature_base64' no es base64 válido") from e
    else:
        challenge = db.scalar(
            select(SigningChallenge)
            .where(SigningChallenge.signature_request_id == request.id)
            .order_by(SigningChallenge.created_at.desc())
            .limit(1)
        )
        if challenge is None:
            raise Conflict("la solicitud no tiene desafíos preparados")
        supplied = None

    if challenge.consumed_at is not None:
        raise Conflict("el desafío ya fue usado")
    if challenge.session_ref != session_ref:
        raise Conflict("el desafío no pertenece a esta sesión")
    if _aware(challenge.expires_at) <= _now():
        raise Conflict("el desafío venció")

    try:
        state = json.loads(ctx.storage.read(f"prepared/{challenge.id}/state.json"))
        prepared_pdf = ctx.storage.read(f"prepared/{challenge.id}/doc.pdf")
    except StorageError as e:
        raise Conflict("el estado de la firma no está disponible: preparar de nuevo") from e
    cert_der = base64.b64decode(state["cert_der"])
    hash_to_sign = base64.b64decode(challenge.hash_to_sign)

    provider = get_provider(request.provider, ctx.settings)
    signer = db.get(Signer, request.signer_id)
    try:
        provider.revalidate_certificate(cert_der, signer)  # vigencia y revocación pueden haber cambiado
    except DomainError as e:
        _fail(ctx, request, e.detail, e.code)
    try:
        signature = provider.obtain_signature(hash_to_sign, supplied)
    except ValueError as e:
        raise Unprocessable(str(e)) from e
    if not verify_hash_signature(cert_der, hash_to_sign, signature):
        _fail(ctx, request, "la firma no verifica contra el hash preparado")

    # El PDF firmado (y su sello) se arma ANTES de consumir el desafío: si la TSA falla no se gasta la
    # firma hecha en el token. La concurrencia sigue protegida por el consumo atómico de más abajo.
    timestamper = timestamping.make_timestamper(ctx.settings)
    stamp: dict = {"status": "absent"}
    try:
        try:
            signed_pdf = finish_pdf(prepared_pdf, state, ax509.Certificate.load(cert_der), signature, timestamper)
            if timestamper is not None:
                stamp = {"status": "embedded"}
        except TimestampUnavailable as e:
            if ctx.settings.tsa_required:
                raise ServiceUnavailable(
                    "la autoridad de sellado de tiempo no está disponible: reintentar",
                    code="timestamp_unavailable",
                ) from e
            stamp = {"status": "unavailable", "reason": str(e)[:200]}
            signed_pdf = finish_pdf(prepared_pdf, state, ax509.Certificate.load(cert_der), signature)
        result_ok = provider.verify_result(signed_pdf, cert_der)
    except ServiceUnavailable:
        raise
    except Exception as e:  # noqa: BLE001 - pyHanko levanta tipos variados
        _fail(ctx, request, f"no se pudo incrustar la firma: {e}")
    if not result_ok:
        _fail(ctx, request, "el PDF firmado no valida contra las anclas de confianza")

    # Consumo atómico: solo una de dos llamadas concurrentes puede ganar.
    now = _now()
    consumed = db.execute(
        update(SigningChallenge)
        .where(
            SigningChallenge.id == challenge.id,
            SigningChallenge.consumed_at.is_(None),
            SigningChallenge.expires_at > now,
        )
        .values(consumed_at=now)
        .execution_options(synchronize_session=False)
    )
    if consumed.rowcount != 1:
        db.rollback()
        raise Conflict("el desafío ya fue usado o venció")

    _register_signed(ctx, request, signed_pdf, stamp, now)

    for name in ("doc.pdf", "state.json"):
        ctx.storage.delete_prepared(f"prepared/{challenge.id}/{name}")
    return request_result(ctx, request, include_bytes=include_bytes)


def document_block(ctx: Ctx, version: DocumentVersion, include_bytes: bool = True) -> dict:
    document = ctx.db.get(Document, version.document_id)
    base = ctx.settings.public_base_url.rstrip("/")
    block = {
        "id": document.id,
        "external_document_id": document.external_document_id,
        "version_number": version.version_number,
        "is_active_version": document.current_version_id == version.id,
        "signing_status": document.signing_status.value,
        "signature_level": version.signature_level.value if version.signature_level else None,
        "download_url": f"{base}/api/v1/documents/{document.id}/versions/"
        f"{version.version_number}/download",
        "signed_document_base64": None,
    }
    if include_bytes:
        block["signed_document_base64"] = base64.b64encode(
            ctx.storage.read(version.storage_ref)
        ).decode()
    return block


def request_result(ctx: Ctx, request: SignatureRequest, include_bytes: bool = True) -> dict:
    db = ctx.db
    result = {
        "id": request.id,
        "document_id": request.document_id,
        "status": request.status.value,
        "provider": request.provider.value,
        "signing_url": signing_url(ctx, request),
        "created_at": request.created_at,
        "certificate": None,
        "document": None,
        "events": [],
    }
    if request.certificate_id is not None:
        cert = db.get(Certificate, request.certificate_id)
        result["certificate"] = {"subject": cert.subject, "serial_number": cert.serial_number}
    signed = db.scalar(
        select(DocumentVersion).where(DocumentVersion.signature_request_id == request.id)
    )
    if signed is not None:
        result["document"] = document_block(ctx, signed, include_bytes=include_bytes)
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.signature_request_id == request.id)
        .order_by(AuditEvent.created_at, AuditEvent.event_type)
    ).all()
    result["events"] = [
        {"event_type": e.event_type, "payload": e.payload, "created_at": e.created_at}
        for e in events
    ]
    return result


def get_request(ctx: Ctx, request_id: uuid.UUID) -> dict:
    return request_result(ctx, _get_request(ctx, request_id))


def get_version_bytes(ctx: Ctx, document_id: uuid.UUID, number: int) -> bytes:
    version = ctx.db.scalar(
        select(DocumentVersion)
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(
            Document.id == document_id,
            Document.integrating_system_id == ctx.system.id,
            DocumentVersion.version_number == number,
        )
    )
    if version is None:
        raise NotFound("versión inexistente")
    try:
        return ctx.storage.read(version.storage_ref)
    except StorageError as e:
        raise NotFound("el binario de la versión no está disponible") from e
