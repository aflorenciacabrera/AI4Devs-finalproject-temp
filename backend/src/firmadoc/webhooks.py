"""Notificaciones al integrador (webhooks): registro, firma, entrega con reintentos y control de SSRF.

Patrón *outbox*: la entrega se registra en la misma transacción que cambia el estado de la solicitud y
un trabajador la envía después, con garantía de "al menos una vez".
"""

import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .errors import Unprocessable
from .models import (
    AuditEvent,
    Certificate,
    DeliveryStatus,
    Document,
    DocumentVersion,
    IntegratingSystem,
    SignatureRequest,
    WebhookDelivery,
)

log = logging.getLogger("firmadoc")

# Espera (en segundos) tras el intento n (1-based) fallido. Seis intentos en total.
BACKOFF_SECONDS = [30, 120, 600, 3600, 21600]
MAX_ATTEMPTS = len(BACKOFF_SECONDS) + 1
LEASE_SECONDS = 60  # reserva de una entrega mientras se envía
BATCH = 50
MAX_URL_LENGTH = 2000

EVENT_SIGNED = "signature.signed"
EVENT_FAILED = "signature.failed"


def invalid_callback(detail: str) -> Unprocessable:
    return Unprocessable(detail, code="invalid_callback_url")


# --- resolución y validación de destinos (SSRF) --------------------------------------------------


def default_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


Resolver = Callable[[str, int], list[str]]
RESOLVER: Resolver = default_resolver  # las pruebas lo reemplazan


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped  # ::ffff:10.0.0.1 se evalúa como 10.0.0.1
    return ip.is_global and not ip.is_multicast


def check_destination(host: str, port: int, settings: Settings, resolver: Resolver | None = None) -> None:
    """Todas las direcciones a las que resuelve el host deben ser públicas."""
    try:
        addresses = (resolver or RESOLVER)(host, port)
    except OSError:
        raise invalid_callback("no se pudo resolver el host de callback_url") from None
    if not addresses:
        raise invalid_callback("el host de callback_url no resuelve a ninguna dirección")
    if settings.webhook_allow_private_hosts:
        return
    for address in addresses:
        if not _is_public(address):
            raise invalid_callback("callback_url apunta a una dirección no pública")


def validate_callback_url(url: str, settings: Settings, resolver: Resolver | None = None) -> None:
    if len(url) > MAX_URL_LENGTH:
        raise invalid_callback("callback_url es demasiado larga")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise invalid_callback("callback_url no es una URL válida") from None
    allowed = {"https", "http"} if settings.webhook_allow_http else {"https"}
    if parts.scheme not in allowed:
        raise invalid_callback("callback_url debe usar https")
    if parts.username is not None or parts.password is not None:
        raise invalid_callback("callback_url no puede incluir credenciales")
    if not parts.hostname:
        raise invalid_callback("callback_url no tiene host")
    check_destination(parts.hostname, port or (443 if parts.scheme == "https" else 80), settings, resolver)


# --- registro de la entrega ---------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _audit(db: Session, request: SignatureRequest, event_type: str, payload: dict) -> None:
    db.add(AuditEvent(signature_request_id=request.id, event_type=event_type, payload=payload))


def build_body(ctx, request: SignatureRequest, delivery: WebhookDelivery, error_code: str | None) -> str:
    """Cuerpo JSON del evento. Se serializa una sola vez y los reintentos reenvían los mismos bytes."""
    from .services import signature_flow as flow  # evita el import circular

    db = ctx.db
    document = db.get(Document, request.document_id)
    payload: dict = {
        "event": delivery.event_type,
        "delivery_id": str(delivery.id),
        "created_at": _aware(delivery.created_at).isoformat(),
        "signature_request": {
            "id": str(request.id),
            "status": request.status.value,
            "provider": request.provider.value,
            "document_id": str(request.document_id),
            "external_document_id": document.external_document_id,
        },
    }
    if delivery.event_type == EVENT_SIGNED:
        version = db.scalar(
            select(DocumentVersion).where(DocumentVersion.signature_request_id == request.id)
        )
        block = flow.document_block(ctx, version, include_bytes=False)
        block.pop("signed_document_base64", None)
        payload["document"] = {**block, "id": str(block["id"])}
        if request.certificate_id is not None:
            cert = db.get(Certificate, request.certificate_id)
            payload["certificate"] = {
                "subject": cert.subject,
                "issuer_subject": cert.issuer_subject,
                "serial_number": cert.serial_number,
            }
    else:
        payload["error"] = {"code": error_code or "failed"}
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def enqueue(ctx, request: SignatureRequest, event_type: str, error_code: str | None = None):
    """Registra la entrega en la transacción en curso (no hace commit). Sin `callback_url`, no hace nada."""
    if not request.callback_url:
        return None
    now = _now()
    delivery = WebhookDelivery(
        id=uuid.uuid4(),
        signature_request_id=request.id,
        url=request.callback_url,
        status=DeliveryStatus.PENDING,
        attempts=0,
        event_type=event_type,
        next_attempt_at=now,
        created_at=now,
    )
    delivery.body = build_body(ctx, request, delivery, error_code)
    ctx.db.add(delivery)
    return delivery


# --- firma y envío ---------------------------------------------------------------------------------


def signature_header(secret: str, body: bytes, timestamp: int) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


def verify_signature(secret: str, body: bytes, header: str, tolerance: int = 300, now: float | None = None) -> bool:
    """Lo que debe hacer el integrador (se usa también en las pruebas y en docs/webhooks.md)."""
    import time

    try:
        fields = dict(part.split("=", 1) for part in header.split(","))
        timestamp = int(fields["t"])
        expected = signature_header(secret, body, timestamp).split("v1=")[1]
        provided = fields["v1"]
    except (KeyError, ValueError):
        return False
    if abs((now if now is not None else time.time()) - timestamp) > tolerance:
        return False
    return hmac.compare_digest(expected, provided)


def deliver(
    db: Session,
    delivery: WebhookDelivery,
    settings: Settings,
    now: datetime | None = None,
    transport: httpx.BaseTransport | None = None,
) -> DeliveryStatus:
    """Un intento de entrega: actualiza el estado, programa el siguiente y audita el resultado final."""
    now = now or _now()
    request = db.get(SignatureRequest, delivery.signature_request_id)
    system = db.get(IntegratingSystem, request.integrating_system_id)
    attempt = delivery.attempts + 1
    status_code: int | None = None
    error: str | None = None
    ok = False
    terminal_failure = False

    if not system.webhook_secret:
        error, terminal_failure = "missing_secret", True
    else:
        body = delivery.body.encode()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Firmadoc-Webhook/1",
            "X-Firmadoc-Event": delivery.event_type,
            "X-Firmadoc-Delivery": str(delivery.id),
            "X-Firmadoc-Signature": signature_header(system.webhook_secret, body, int(now.timestamp())),
        }
        try:
            parts = urlsplit(delivery.url)
            check_destination(
                parts.hostname or "", parts.port or (443 if parts.scheme == "https" else 80), settings
            )
            with httpx.Client(
                timeout=settings.webhook_timeout_seconds, follow_redirects=False, transport=transport
            ) as client, client.stream("POST", delivery.url, content=body, headers=headers) as response:
                status_code = response.status_code  # el cuerpo de la respuesta nunca se lee
            ok = 200 <= status_code < 300
            if not ok:
                error = f"HTTP {status_code}"
        except Unprocessable:
            error = "destino no permitido"
        except httpx.HTTPError as e:
            error = type(e).__name__  # sin el mensaje: podría incluir la URL
        except ValueError:
            error = "URL inválida"

    delivery.attempts = attempt
    delivery.last_attempt_at = now
    delivery.response_status = status_code
    delivery.last_error = None if ok else error
    if ok:
        delivery.status = DeliveryStatus.DELIVERED
        delivery.next_attempt_at = None
        _audit(db, request, "webhook_delivered", {"delivery_id": str(delivery.id), "attempts": attempt})
    elif terminal_failure or attempt >= MAX_ATTEMPTS:
        delivery.status = DeliveryStatus.FAILED
        delivery.next_attempt_at = None
        _audit(
            db,
            request,
            "webhook_failed",
            {"delivery_id": str(delivery.id), "attempts": attempt, "reason": error},
        )
    else:
        delivery.next_attempt_at = now + timedelta(seconds=BACKOFF_SECONDS[attempt - 1])
    db.commit()
    return delivery.status


def run_due(
    db: Session,
    settings: Settings,
    now: datetime | None = None,
    transport: httpx.BaseTransport | None = None,
) -> int:
    """Envía las entregas vencidas. Devuelve cuántas intentó. Reserva cada una con un UPDATE atómico."""
    now = now or _now()
    ids = db.scalars(
        select(WebhookDelivery.id)
        .where(WebhookDelivery.status == DeliveryStatus.PENDING, WebhookDelivery.next_attempt_at <= now)
        .order_by(WebhookDelivery.next_attempt_at)
        .limit(BATCH)
    ).all()
    attempted = 0
    for delivery_id in ids:
        try:
            claimed = db.execute(
                update(WebhookDelivery)
                .where(
                    WebhookDelivery.id == delivery_id,
                    WebhookDelivery.status == DeliveryStatus.PENDING,
                    WebhookDelivery.next_attempt_at <= now,
                )
                .values(next_attempt_at=now + timedelta(seconds=LEASE_SECONDS))
                .execution_options(synchronize_session=False)
            ).rowcount
            db.commit()
        except OperationalError:  # otra ejecución tiene la base ocupada: ya la está procesando
            db.rollback()
            continue
        if claimed != 1:
            continue
        db.expire_all()
        delivery = db.get(WebhookDelivery, delivery_id)
        deliver(db, delivery, settings, now=now, transport=transport)
        attempted += 1
    return attempted


# --- trabajador en segundo plano ------------------------------------------------------------------


class WebhookWorker:
    def __init__(self, settings: Settings, session_factory: sessionmaker[Session]):
        self.settings = settings
        self.session_factory = session_factory
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="webhook-worker", daemon=True)

    def start(self) -> "WebhookWorker":
        self._thread.start()
        return self

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        self._thread.join(timeout)

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def _loop(self) -> None:
        while not self._stop.wait(self.settings.webhook_poll_seconds):
            try:
                with self.session_factory() as db:
                    run_due(db, self.settings)
            except Exception:
                log.exception("error en el trabajador de webhooks")
