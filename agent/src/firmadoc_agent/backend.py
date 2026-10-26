"""Acceso al token (interfaz) y tipos comunes."""

import base64
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# Prefijo ASN.1 de DigestInfo para SHA-256 (RFC 8017, sección 9.2): 19 bytes + hash de 32.
DIGEST_INFO_SHA256 = bytes.fromhex("3031300d060960864801650304020105000420")
SHA256_LEN = 32


def digest_info(sha256: bytes) -> bytes:
    """Lo que el token firma con `CKM_RSA_PKCS`: el DigestInfo del hash (docs/agent-contract.md)."""
    if len(sha256) != SHA256_LEN:
        raise ValueError("se esperaba un hash SHA-256 de 32 bytes")
    return DIGEST_INFO_SHA256 + sha256


@dataclass(frozen=True)
class TokenCertificate:
    id: str  # CKA_ID en hexadecimal
    token_label: str
    subject: str
    issuer: str
    serial_number: str
    not_before: datetime
    not_after: datetime
    der: bytes

    def pem(self) -> str:
        body = base64.encodebytes(self.der).decode().strip()
        return f"-----BEGIN CERTIFICATE-----\n{body}\n-----END CERTIFICATE-----\n"


@dataclass(frozen=True)
class TokenInfo:
    """Lo que `diagnose` muestra de un token (todo sin PIN)."""

    label: str
    manufacturer: str
    model: str
    serial: str
    flags: list[str]
    certificates: list[tuple[TokenCertificate, bool]]  # (certificado, ¿es de AC?)


class TokenBackend(Protocol):
    """Todo lo que el agente necesita del token. Las implementaciones lanzan `AgentError`."""

    def list_certificates(self) -> list[TokenCertificate]:
        """Certificados de usuario del token, sin PIN. Omite los de AC."""

    def inspect(self) -> list[TokenInfo]:
        """Tokens y todos sus certificados (incluidos los de AC), sin abrir sesión con PIN."""

    def final_try(self, certificate_id: str) -> bool:
        """¿Queda un único intento de PIN antes del bloqueo?"""

    def sign(self, certificate_id: str, pin: str, digests: list[bytes]) -> list[bytes]:
        """Un solo login, firma cada hash (DigestInfo, RSA PKCS#1 v1.5) y cierra la sesión.

        Debe hacer exactamente un intento de login y no devolver firmas parciales.
        """
