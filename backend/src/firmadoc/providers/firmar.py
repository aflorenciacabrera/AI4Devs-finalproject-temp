"""Proveedor `firmar`: firma remota. El servicio recibe el PDF completo, firma con una clave que
Firmadoc nunca ve y devuelve el resultado por callback (ver docs/firmar.md)."""

import base64
import hashlib
import hmac
from dataclasses import dataclass

import httpx

from ..config import Settings
from ..errors import ServiceUnavailable
from ..models import Provider

TRANSPORT: httpx.BaseTransport | None = None  # las pruebas lo reemplazan (p. ej. por ASGI)
SIGNATURE_HEADER = "X-Firmar-Signature"


def remote_unavailable() -> ServiceUnavailable:
    # Mensaje genérico: nunca se reproduce el cuerpo del servicio (ni se filtran sus detalles).
    return ServiceUnavailable("el servicio de firma remota no está disponible", code="remote_unavailable")


def callback_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_callback_signature(secret: str, body: bytes, header: str | None) -> bool:
    return bool(header) and hmac.compare_digest(callback_signature(secret, body), header.strip())


@dataclass(frozen=True)
class RemoteOperation:
    operation_id: str
    authorization_url: str


class RemoteProvider:
    """Marca del proveedor `firmar`: no firma hashes (no implementa `SignatureProvider`)."""

    provider = Provider.FIRMAR


class FirmarClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.base = (settings.firmar_base_url or "").rstrip("/")
        self.transport = transport or TRANSPORT

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=self.settings.firmar_timeout_seconds, follow_redirects=False, transport=self.transport
        )

    def submit(self, pdf: bytes, signer_cuil: str, callback_url: str) -> RemoteOperation:
        """OAuth2 client credentials y envío del documento. Cualquier problema es `remote_unavailable`."""
        settings = self.settings
        try:
            with self._client() as client:
                token = client.post(
                    f"{self.base}/oauth/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": settings.firmar_client_id,
                        "client_secret": settings.firmar_client_secret or "",
                    },
                )
                token.raise_for_status()
                access_token = token.json()["access_token"]
                response = client.post(
                    f"{self.base}/v1/operations",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={
                        "document_base64": base64.b64encode(pdf).decode(),
                        "signer_cuil": signer_cuil,
                        "callback_url": callback_url,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return RemoteOperation(str(data["operation_id"]), str(data["authorization_url"]))
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            raise remote_unavailable() from None
