"""Datos de demostración. Uso: `python -m firmadoc.seed`."""

import hashlib
import io
from datetime import UTC, datetime, timedelta

from pyhanko.pdf_utils import writer as pw
from pyhanko.pdf_utils.generic import StreamObject
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
from .storage import DatabaseStorage, DocumentStorage, LocalFileStorage

DEMO_SYSTEM_NAME = "Sistema de demostración"
DEMO_WEBHOOK_SECRET = "whsec_demo_solo_para_desarrollo"
DEMO_API_KEY = "firmadoc-demo-key"  # solo demo; en la base queda únicamente el hash


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def demo_pdf(text: str) -> bytes:
    """PDF mínimo y válido para los documentos de demostración (sin firma real)."""
    writer = pw.PdfFileWriter()
    contents = writer.add_object(StreamObject(stream_data=f"BT 72 720 Td ({text}) Tj ET".encode()))
    writer.insert_page(pw.PageObject(contents=contents, media_box=(0, 0, 595, 842)))
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def seed_demo(session: Session, storage: DocumentStorage | None = None) -> bool:
    """Crea los datos de demo. Idempotente: devuelve False si ya existían.

    Con `storage` guarda además dos PDF reales (v1 y v2) y registra su hash verdadero; sin él las versiones
    de demostración solo tienen datos (hash de un texto fijo) y no tienen binario. La v2 de demostración
    NO tiene firma criptográfica: para ver una firma real se usa el flujo de firma.
    """
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

    pdf1 = demo_pdf("Documento de demostracion v1") if storage else b"demo-v1"
    pdf2 = demo_pdf("Documento de demostracion v2 (sin firma criptografica)") if storage else b"demo-v2"
    if storage is not None:
        storage.save("demo/EXP-DEMO-001/v1.pdf", pdf1)
        storage.save("demo/EXP-DEMO-001/v2.pdf", pdf2)
    v1 = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        origin=VersionOrigin.UPLOADED,
        storage_ref="demo/EXP-DEMO-001/v1.pdf",
        document_hash=hashlib.sha256(pdf1).hexdigest(),
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
        document_hash=hashlib.sha256(pdf2).hexdigest(),
    )
    session.add(v2)
    session.flush()

    doc.current_version_id = v2.id
    doc.signing_status = SigningStatus.SIGNED
    session.commit()
    return True


def main() -> None:
    settings = get_settings()
    if settings.real_mode:
        raise SystemExit(
            "El seed es de demostración y no se carga en modo real. "
            "Crear integradores con: python -m firmadoc.integrators create --help"
        )
    engine = make_engine(settings.database_url)
    with make_session_factory(engine)() as session:
        storage: DocumentStorage = (
            DatabaseStorage(session)
            if settings.storage_backend == "database"
            else LocalFileStorage(settings.storage_dir)
        )
        print("Seed aplicado." if seed_demo(session, storage) else "El seed ya estaba aplicado.")


if __name__ == "__main__":
    main()
