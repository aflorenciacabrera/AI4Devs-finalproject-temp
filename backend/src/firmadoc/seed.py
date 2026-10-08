"""Datos de demostración. Uso: `python -m firmadoc.seed`."""

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import make_engine, make_session_factory
from .models import (
    Certificate,
    Document,
    DocumentVersion,
    IntegratingSystem,
    Provider,
    RequestStatus,
    RevocationStatus,
    SignatureLevel,
    SignatureRequest,
    Signer,
    SigningStatus,
    VersionOrigin,
)

DEMO_SYSTEM_NAME = "Sistema de demostración"
DEMO_WEBHOOK_SECRET = "whsec_demo_solo_para_desarrollo"
DEMO_API_KEY = "firmadoc-demo-key"  # solo demo; en la base queda únicamente el hash


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def seed_demo(session: Session) -> bool:
    """Crea los datos de demo. Idempotente: devuelve False si ya existían."""
    if session.scalar(select(IntegratingSystem).where(IntegratingSystem.name == DEMO_SYSTEM_NAME)):
        return False

    now = datetime.now(UTC)
    system = IntegratingSystem(
        name=DEMO_SYSTEM_NAME,
        api_key_hash=hash_api_key(DEMO_API_KEY),
        allowed_origins="http://localhost:4200",
        webhook_secret=DEMO_WEBHOOK_SECRET,
    )
    signer = Signer(full_name="Firmante de Prueba", identifier="20000000001", email="demo@example.org")
    session.add_all([system, signer])
    session.flush()

    cert = Certificate(
        signer_id=signer.id,
        subject="CN=Firmante de Prueba,serialNumber=CUIL 20000000001",
        issuer_subject="CN=Firmadoc Demo CA",
        cuil="20000000001",
        serial_number="DEMO-0001",
        provider=Provider.LOCAL,
        revocation_status=RevocationStatus.GOOD,
        issued_at=now,
        expires_at=now + timedelta(days=365),
    )
    doc = Document(
        integrating_system_id=system.id,
        external_document_id="EXP-DEMO-001",
        signing_status=SigningStatus.PENDING_SIGNATURE,
    )
    session.add_all([cert, doc])
    session.flush()

    v1 = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        origin=VersionOrigin.UPLOADED,
        storage_ref="demo/EXP-DEMO-001/v1.pdf",
        document_hash=hashlib.sha256(b"demo-v1").hexdigest(),
    )
    request = SignatureRequest(
        document_id=doc.id,
        integrating_system_id=system.id,
        signer_id=signer.id,
        certificate_id=cert.id,
        provider=Provider.LOCAL,
        status=RequestStatus.SIGNED,
        signed_at=now,
    )
    session.add_all([v1, request])
    session.flush()

    v2 = DocumentVersion(
        document_id=doc.id,
        version_number=2,
        origin=VersionOrigin.SIGNED,
        signature_request_id=request.id,
        signature_level=SignatureLevel.B_B,
        storage_ref="demo/EXP-DEMO-001/v2.pdf",
        document_hash=hashlib.sha256(b"demo-v2").hexdigest(),
    )
    session.add(v2)
    session.flush()

    doc.current_version_id = v2.id
    doc.signing_status = SigningStatus.SIGNED
    session.commit()
    return True


def main() -> None:
    engine = make_engine(get_settings().database_url)
    with make_session_factory(engine)() as session:
        print("Seed aplicado." if seed_demo(session) else "El seed ya estaba aplicado.")


if __name__ == "__main__":
    main()
