from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from ..models import Certificate, Provider, Signer


@dataclass(frozen=True)
class ResolvedCertificate:
    record: Certificate  # fila registrada en la base
    der: bytes  # certificado completo para incrustar en la firma


class SignatureProvider(Protocol):
    """Quién produce la firma. El PDF y el flujo son comunes a todos los proveedores."""

    provider: Provider

    def resolve_certificate(
        self, db: Session, certificate_pem: str | None, signer: Signer
    ) -> ResolvedCertificate:
        """Certificado con el que se firmará (público). Lo valida o lo genera según el proveedor."""

    def revalidate_certificate(self, cert_der: bytes, signer: Signer) -> None:
        """Se invoca al completar: el certificado puede haberse vencido o revocado desde `prepare`."""

    def verify_result(self, pdf: bytes, cert_der: bytes) -> bool:
        """¿La firma recién incrustada valida contra las anclas que corresponden al proveedor?"""

    def obtain_signature(self, hash_to_sign: bytes, supplied: bytes | None) -> bytes:
        """Firma del hash: la produce el propio proveedor (`local`) o llega del cliente (`token`)."""
