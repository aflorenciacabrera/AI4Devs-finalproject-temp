from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from ..models import Certificate, Provider


@dataclass(frozen=True)
class ResolvedCertificate:
    record: Certificate  # fila registrada en la base
    der: bytes  # certificado completo para incrustar en la firma


class SignatureProvider(Protocol):
    """Quién produce la firma. El PDF y el flujo son comunes a todos los proveedores."""

    provider: Provider

    def resolve_certificate(self, db: Session, certificate_pem: str | None) -> ResolvedCertificate:
        """Certificado con el que se firmará (público). Lo valida o lo genera según el proveedor."""

    def obtain_signature(self, hash_to_sign: bytes, supplied: bytes | None) -> bytes:
        """Firma del hash: la produce el propio proveedor (`local`) o llega del cliente (`token`)."""
