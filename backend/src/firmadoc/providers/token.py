"""Proveedor `token`: la clave privada queda en el token del usuario; el servidor solo ve el
certificado público y las firmas de los hashes (ver docs/agent-contract.md)."""

from asn1crypto import pem
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..certificate_validation import CertificateChecker, invalid
from ..models import Certificate, Provider, Signer
from ..pdf_engine import verify_last_signature
from ..trust import TrustStore
from .base import ResolvedCertificate


def _pem_to_der(certificate_pem: str) -> bytes:
    data = certificate_pem.encode()
    if not pem.detect(data):
        raise invalid("'certificate_pem' no es un certificado PEM")
    try:
        return pem.unarmor(data)[2]
    except ValueError as e:
        raise invalid("'certificate_pem' no es un certificado PEM válido") from e


class TokenAgentProvider:
    provider = Provider.TOKEN

    def __init__(self, checker: CertificateChecker, trust: TrustStore, require_cuil_match: bool = False):
        self.checker = checker
        self.trust = trust
        self.require_cuil_match = require_cuil_match

    def _expected_cuil(self, signer: Signer) -> str | None:
        """Solo con `FIRMADOC_REQUIRE_CUIL_MATCH`: por defecto firma quien tiene el token y su PIN."""
        return signer.identifier if self.require_cuil_match else None

    def resolve_certificate(
        self, db: Session, certificate_pem: str | None, signer: Signer
    ) -> ResolvedCertificate:
        if not certificate_pem:
            raise invalid("falta 'certificate_pem': el proveedor token necesita el certificado")
        der = _pem_to_der(certificate_pem)
        validated = self.checker.validate(der, self._expected_cuil(signer))

        record = db.scalar(
            select(Certificate).where(Certificate.serial_number == validated.serial_number)
        )
        if record is None:
            record = Certificate(
                signer_id=signer.id,
                subject=validated.subject,
                issuer_subject=validated.issuer_subject,
                cuil=validated.cuil,
                serial_number=validated.serial_number,
                provider=Provider.TOKEN,
                revocation_status=validated.revocation_status,
                issued_at=validated.not_before,
                expires_at=validated.not_after,
            )
            db.add(record)
        elif record.issuer_subject != validated.issuer_subject:
            raise invalid("el número de serie ya está registrado para otro emisor")
        else:
            record.revocation_status = validated.revocation_status
        db.flush()
        return ResolvedCertificate(record, der)

    def revalidate_certificate(self, cert_der: bytes, signer: Signer) -> None:
        self.checker.validate(cert_der, self._expected_cuil(signer))

    def verify_result(self, pdf: bytes, cert_der: bytes) -> bool:
        return verify_last_signature(pdf, self.trust.roots, self.trust.intermediates)

    def obtain_signature(self, hash_to_sign: bytes, supplied: bytes | None) -> bytes:
        if supplied is None:
            raise ValueError("la firma del token es obligatoria: el servidor no tiene la clave")
        return supplied
