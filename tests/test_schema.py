from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from sqlalchemy import delete, inspect, select, update
from sqlalchemy.exc import DBAPIError

from firmadoc.db import make_engine
from firmadoc.models import (
    AuditEvent,
    Certificate,
    Document,
    DocumentVersion,
    IntegratingSystem,
    Provider,
    SignatureRequest,
    Signer,
    SigningChallenge,
    VersionOrigin,
)
from firmadoc.seed import DEMO_SYSTEM_NAME, seed_demo

from .conftest import alembic_config

TABLES = {
    "integrating_system", "document", "document_version", "signature_request",
    "signing_challenge", "signature_batch", "signer", "certificate", "audit_event",
    "webhook_delivery",
}


def _now():
    return datetime.now(UTC)


@pytest.fixture
def base(session):
    """Sistema, firmante, certificado, documento y solicitud mínimos."""
    system = IntegratingSystem(name="s", api_key_hash="h1")
    signer = Signer(full_name="F", identifier="20000000001", email="f@x.org")
    session.add_all([system, signer])
    session.flush()
    cert = Certificate(
        signer_id=signer.id, subject="s", issuer_subject="i", serial_number="SN1",
        provider=Provider.LOCAL, issued_at=_now(), expires_at=_now() + timedelta(days=1),
    )
    doc = Document(integrating_system_id=system.id)
    session.add_all([cert, doc])
    session.flush()
    req = SignatureRequest(
        document_id=doc.id, integrating_system_id=system.id, signer_id=signer.id,
        provider=Provider.LOCAL,
    )
    session.add(req)
    session.flush()
    session.commit()
    return {"system": system, "signer": signer, "cert": cert, "doc": doc, "req": req}


def _version(doc, n):
    return DocumentVersion(
        document_id=doc.id, version_number=n, origin=VersionOrigin.UPLOADED,
        storage_ref=f"x/v{n}", document_hash="h",
    )


def test_upgrade_y_downgrade(db_url):
    cfg = alembic_config(db_url)
    command.upgrade(cfg, "head")
    engine = make_engine(db_url)
    assert TABLES <= set(inspect(engine).get_table_names())
    engine.dispose()
    command.downgrade(cfg, "base")
    engine = make_engine(db_url)
    assert not TABLES & set(inspect(engine).get_table_names())
    engine.dispose()


def test_document_version_inmutable(session, base):
    v = _version(base["doc"], 1)
    session.add(v)
    session.commit()
    with pytest.raises(DBAPIError, match="inmutable"):
        session.execute(update(DocumentVersion).values(storage_ref="otro"))
    session.rollback()
    with pytest.raises(DBAPIError, match="inmutable"):
        session.execute(delete(DocumentVersion))
    session.rollback()


def test_version_number_duplicado(session, base):
    session.add(_version(base["doc"], 1))
    session.commit()
    session.add(_version(base["doc"], 1))
    with pytest.raises(DBAPIError):
        session.commit()
    session.rollback()


def test_nueva_version_vigente_no_toca_versiones(session, base):
    doc = base["doc"]
    v1, v2 = _version(doc, 1), _version(doc, 2)
    session.add_all([v1, v2])
    session.commit()
    doc.current_version_id = v1.id
    session.commit()
    doc.current_version_id = v2.id
    session.commit()
    assert session.get(Document, doc.id).current_version_id == v2.id
    assert session.get(DocumentVersion, v1.id).storage_ref == "x/v1"


def test_audit_event_append_only(session, base):
    session.add(AuditEvent(signature_request_id=base["req"].id, event_type="created"))
    session.commit()
    with pytest.raises(DBAPIError, match="inmutable"):
        session.execute(update(AuditEvent).values(event_type="x"))
    session.rollback()
    with pytest.raises(DBAPIError, match="inmutable"):
        session.execute(delete(AuditEvent))
    session.rollback()


def test_audit_event_exige_exactamente_una_referencia(session, base):
    session.add(AuditEvent(event_type="sin_ref"))
    with pytest.raises(DBAPIError):
        session.commit()
    session.rollback()


def test_desafio_consumido_no_se_modifica(session, base):
    ch = SigningChallenge(
        signature_request_id=base["req"].id, certificate_id=base["cert"].id,
        hash_to_sign="abc", session_ref="sess", expires_at=_now() + timedelta(minutes=5),
    )
    session.add(ch)
    session.commit()
    ch.consumed_at = _now()  # primer uso: permitido
    session.commit()
    with pytest.raises(DBAPIError, match="consumido"):
        session.execute(update(SigningChallenge).values(consumed_at=None))
    session.rollback()


def test_unicidad_serial_y_api_key(session, base):
    session.add(Certificate(
        subject="s", issuer_subject="i", serial_number="SN1", provider=Provider.TOKEN,
        issued_at=_now(), expires_at=_now(),
    ))
    with pytest.raises(DBAPIError):
        session.commit()
    session.rollback()
    session.add(IntegratingSystem(name="otro", api_key_hash="h1"))
    with pytest.raises(DBAPIError):
        session.commit()
    session.rollback()


def test_seed_idempotente(session):
    assert seed_demo(session) is True
    assert seed_demo(session) is False
    systems = session.scalars(
        select(IntegratingSystem).where(IntegratingSystem.name == DEMO_SYSTEM_NAME)
    ).all()
    assert len(systems) == 1
    doc = session.scalars(select(Document)).one()
    assert len(doc.versions) == 2
    assert doc.current_version_id is not None
    assert systems[0].api_key_hash != "firmadoc-demo-key"
