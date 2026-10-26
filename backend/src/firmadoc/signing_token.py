"""Token del widget: credencial acotada a una única solicitud de firma y de vida corta.

Formato: `base64url(payload).base64url(HMAC-SHA256(secret, payload))` con
`payload = {"rid": <id de la solicitud>, "exp": <epoch en segundos>}`. Sin estado: no se guarda
nada en la base de datos. Solo habilita los endpoints del widget (nunca los de integración).
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid

from .config import Settings
from .errors import Unauthorized

log = logging.getLogger("firmadoc")
_ephemeral_secret: str | None = None


def secret_for(settings: Settings) -> str:
    """Secreto configurado o, si falta, uno efímero (los tokens dejan de valer al reiniciar)."""
    global _ephemeral_secret
    if settings.signing_secret:
        return settings.signing_secret
    if _ephemeral_secret is None:
        _ephemeral_secret = secrets.token_urlsafe(48)
        log.warning(
            "FIRMADOC_SIGNING_SECRET no está configurado: se usa un secreto efímero y los "
            "enlaces de firma dejarán de valer al reiniciar el servidor"
        )
    return _ephemeral_secret


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(secret: str, payload: bytes) -> bytes:
    return hmac.new(secret.encode(), payload, hashlib.sha256).digest()


def issue(secret: str, request_id: uuid.UUID, ttl_seconds: int, now: float | None = None) -> str:
    exp = int((now if now is not None else time.time()) + ttl_seconds)
    payload = json.dumps({"rid": str(request_id), "exp": exp}, separators=(",", ":")).encode()
    return f"{_b64(payload)}.{_b64(_sign(secret, payload))}"


def invalid() -> Unauthorized:
    return Unauthorized("el enlace de firma no es válido o venció", code="invalid_token")


def verify(secret: str, token: str, request_id: uuid.UUID, now: float | None = None) -> dict:
    """Devuelve el contenido del token o lanza `Unauthorized` (`invalid_token`)."""
    try:
        encoded_payload, encoded_mac = token.split(".")
        payload = _unb64(encoded_payload)
        mac = _unb64(encoded_mac)
        data = json.loads(payload)
    except (ValueError, TypeError):
        raise invalid() from None
    if not hmac.compare_digest(mac, _sign(secret, payload)):
        raise invalid()
    if not isinstance(data, dict) or data.get("rid") != str(request_id):
        raise invalid()
    exp = data.get("exp")
    if not isinstance(exp, int) or exp <= (now if now is not None else time.time()):
        raise invalid()
    return data
