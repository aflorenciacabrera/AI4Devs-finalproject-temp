"""Registros estructurados (una línea JSON por evento) con un identificador de pedido.

Sirven para investigar qué pasó con una firma concreta: cada pedido HTTP recibe un identificador que
acompaña a todos los registros que produce, se devuelve en la cabecera `X-Request-ID` y puede venir del
sistema integrador para unir sus registros con los de Firmadoc.

Qué NO se registra nunca: el PIN (no llega al servidor), tokens, API keys, secretos, el contenido de los
documentos, firmas ni certificados, la cadena de consulta de la URL, y datos personales del firmante
(nombre, CUIL, correo). Los eventos llevan identificadores, no personas; quién firmó está en la auditoría.
Ver docs/observability.md.
"""

import contextvars
import json
import logging
import re
import sys
import time
import uuid
from datetime import UTC, datetime

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
LOGGER = "firmadoc"
# Solo se acepta un identificador ajeno con esta forma: nunca se copia a los registros un texto arbitrario.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
# Red de seguridad: si alguien pasa uno de estos campos a `log_event`, se omite su valor.
_SENSITIVE = re.compile(r"pin|password|secret|token|api_?key|authorization|base64|pem|cuil|email|identifier", re.IGNORECASE)
OMITTED = "[omitido]"
# Claves del detalle de auditoría que pueden copiarse a los registros (escalares, sin datos personales).
AUDIT_FIELDS = ("provider", "code", "documents", "signed", "errors", "signature_level")

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("firmadoc_request_id", default=None)
_http = logging.getLogger(f"{LOGGER}.http")
_events = logging.getLogger(f"{LOGGER}.events")


def current_request_id() -> str | None:
    return _request_id.get()


def new_request_id() -> str:
    return uuid.uuid4().hex


def accept_request_id(value: str | None) -> str:
    """El identificador que mandó quien llama, si tiene una forma segura; si no, uno nuevo."""
    return value if value and _VALID_REQUEST_ID.match(value) else new_request_id()


def _safe(fields: dict) -> dict:
    return {k: (OMITTED if _SENSITIVE.search(k) else v) for k, v in fields.items() if v is not None}


class JsonFormatter(logging.Formatter):
    """Una línea JSON por registro: `ts`, `level`, `logger`, `event`, `request_id` y los campos del evento."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        request_id = current_request_id()
        if request_id:
            entry["request_id"] = request_id
        entry.update(_safe(getattr(record, "fields", None) or {}))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Los mismos datos en una línea legible, para desarrollo (`FIRMADOC_LOG_FORMAT=text`)."""

    def format(self, record: logging.LogRecord) -> str:
        fields = _safe(getattr(record, "fields", None) or {})
        request_id = current_request_id()
        if request_id:
            fields = {"request_id": request_id, **fields}
        extra = " ".join(f"{k}={v}" for k, v in fields.items())
        line = f"{record.levelname:<7} {record.name} {record.getMessage()} {extra}".rstrip()
        return line + ("\n" + self.formatException(record.exc_info) if record.exc_info else "")


def configure_logging(log_format: str = "json", level: str = "INFO") -> None:
    """Deja un único manejador en el logger `firmadoc` (salida estándar). Se puede llamar más de una vez."""
    logger = logging.getLogger(LOGGER)
    for handler in [h for h in logger.handlers if getattr(h, "_firmadoc", False)]:
        logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if log_format == "json" else TextFormatter())
    handler._firmadoc = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False  # sin duplicados si el proceso también configuró el logger raíz


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    """Registra un evento del dominio (p. ej. `audit.signed`) con sus identificadores."""
    _events.log(level, event, extra={"fields": fields})


def log_audit(event_type: str, payload: dict | None = None, **ids) -> None:
    """Acompaña cada evento de auditoría con un registro: el identificador del pedido une los dos mundos.

    La auditoría (tabla `audit_event`) sigue siendo la fuente de verdad; esto es para investigar. Si la
    transacción se deshace, el registro queda y el evento de auditoría no.
    """
    detail = {k: v for k, v in (payload or {}).items() if k in AUDIT_FIELDS and isinstance(v, (str, int, bool))}
    log_event(f"audit.{event_type}", **{k: str(v) for k, v in ids.items() if v is not None}, **detail)


class RequestContextMiddleware:
    """Asigna el identificador del pedido, lo devuelve en `X-Request-ID` y registra el pedido al terminar.

    Se registran el método, la ruta declarada (`/api/v1/.../{request_id}/complete`), la ruta pedida, el
    estado y la duración. La cadena de consulta no se registra. `/health` se registra en nivel `debug`.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = accept_request_id(Headers(scope=scope).get(REQUEST_ID_HEADER))
        token = _request_id.set(request_id)
        started = time.perf_counter()
        status = 500  # si la aplicación falla antes de responder

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            route = getattr(scope.get("route"), "path", None)
            level = logging.DEBUG if scope["path"] == "/health" else logging.INFO
            _http.log(
                level,
                "http_request",
                extra={
                    "fields": {
                        "method": scope["method"],
                        "route": route or "(sin ruta)",
                        "path": scope["path"][:200],
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                },
            )
            _request_id.reset(token)
