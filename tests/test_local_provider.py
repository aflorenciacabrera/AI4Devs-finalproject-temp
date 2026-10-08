from sqlalchemy import select

from firmadoc.models import Certificate, Provider
from firmadoc.pdf_engine import verify_hash_signature
from firmadoc.providers.local import CERT_FILE, KEY_FILE, LocalPAdESProvider


def test_primer_uso_crea_certificado(tmp_path, session):
    cert_dir = tmp_path / "cert"
    assert not cert_dir.exists()
    resolved = LocalPAdESProvider(cert_dir).resolve_certificate(session, None)
    session.commit()
    assert (cert_dir / KEY_FILE).exists() and (cert_dir / CERT_FILE).exists()
    assert resolved.record.provider == Provider.LOCAL


def test_reinicio_reutiliza_el_certificado(tmp_path, session):
    cert_dir = tmp_path / "cert"
    first = LocalPAdESProvider(cert_dir).resolve_certificate(session, None)
    session.commit()
    restarted = LocalPAdESProvider(cert_dir).resolve_certificate(session, None)  # nueva instancia
    session.commit()
    assert restarted.der == first.der
    assert restarted.record.id == first.record.id
    assert len(session.scalars(select(Certificate)).all()) == 1


def test_firma_del_hash_verifica(tmp_path, session):
    provider = LocalPAdESProvider(tmp_path / "cert")
    resolved = provider.resolve_certificate(session, None)
    digest = bytes(range(32))
    signature = provider.obtain_signature(digest, None)
    assert verify_hash_signature(resolved.der, digest, signature)
    assert not verify_hash_signature(resolved.der, bytes(32), signature)


def test_firma_suministrada_se_respeta(tmp_path):
    assert LocalPAdESProvider(tmp_path).obtain_signature(bytes(32), b"del-cliente") == b"del-cliente"
