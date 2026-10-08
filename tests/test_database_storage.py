"""Almacén de documentos en la base de datos: integridad, inmutabilidad, atomicidad, flujo completo y migración."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import DBAPIError

from firmadoc.config import Settings
from firmadoc.db import make_engine
from firmadoc.models import DocumentVersion, StoredBlob
from firmadoc.storage import DatabaseStorage, StorageError, sha256_hex
from firmadoc.storage_migrate import migrate

from .agent_simulator import AgentSimulator
from .conftest import alembic_config
from .test_firmar import approve, firmar_env, prepared  # noqa: F401 (fixture reutilizada)
from .test_flow import create, sign_fully
from .test_signature_batches import create_batch
from .test_token_flow import run_token_flow, signer_identity

PDF = b"%PDF-1.4\n% contenido de prueba\n"


def blobs(session) -> list[str]:
    session.expire_all()
    return list(session.scalars(select(StoredBlob.ref).order_by(StoredBlob.ref)))


def drop_protection(session, dialect: str) -> None:
    """Quita el trigger de UPDATE para simular a alguien que altera la base a mano."""
    if dialect == "postgresql":
        session.execute(text("ALTER TABLE stored_blob DISABLE TRIGGER stored_blob_protect"))
    else:
        session.execute(text("DROP TRIGGER stored_blob_no_update"))


# --- configuración -----------------------------------------------------------------------------------


def test_backend_por_defecto_y_validacion():
    assert Settings().storage_backend == "files"
    assert Settings(storage_backend="database").storage_backend == "database"
    with pytest.raises(ValueError):
        Settings(storage_backend="s3")


# --- el almacén -----------------------------------------------------------------------------------------


def test_ida_y_vuelta(session):
    storage = DatabaseStorage(session)
    storage.save("documents/a/v1.pdf", PDF)
    session.commit()
    assert DatabaseStorage(session).read("documents/a/v1.pdf") == PDF
    row = session.get(StoredBlob, "documents/a/v1.pdf")
    assert row.size == len(PDF) and row.sha256 == sha256_hex(PDF)


def test_no_sobrescribe(session):
    storage = DatabaseStorage(session)
    storage.save("documents/a/v1.pdf", b"original")
    session.commit()
    with pytest.raises(StorageError):
        storage.save("documents/a/v1.pdf", b"otro")
    session.rollback()
    assert storage.read("documents/a/v1.pdf") == b"original"


def test_inexistente(session):
    with pytest.raises(StorageError):
        DatabaseStorage(session).read("documents/no/existe.pdf")


@pytest.mark.parametrize("ref", ["../fuera.pdf", "documents/../../fuera.pdf", "/etc/passwd", "", "a\\b.pdf"])
def test_referencias_invalidas(session, ref):
    storage = DatabaseStorage(session)
    with pytest.raises(StorageError):
        storage.save(ref, b"x")
    with pytest.raises(StorageError):
        storage.read(ref)


def test_hash_alterado_se_detecta(session, engine):
    storage = DatabaseStorage(session)
    storage.save("documents/a/v1.pdf", PDF)
    session.commit()
    drop_protection(session, engine.dialect.name)
    session.execute(text("UPDATE stored_blob SET content = :c WHERE ref = 'documents/a/v1.pdf'"), {"c": b"alterado"})
    session.commit()
    session.expire_all()
    with pytest.raises(StorageError, match="no coincide"):
        DatabaseStorage(session).read("documents/a/v1.pdf")


# --- inmutabilidad ----------------------------------------------------------------------------------------


def test_triggers_de_inmutabilidad(session):
    storage = DatabaseStorage(session)
    storage.save("documents/a/v1.pdf", PDF)
    storage.save("prepared/x/doc.pdf", PDF)
    session.commit()

    with pytest.raises(DBAPIError):
        session.execute(text("UPDATE stored_blob SET size = 1"))
    session.rollback()
    with pytest.raises(DBAPIError):
        session.execute(text("DELETE FROM stored_blob WHERE ref = 'documents/a/v1.pdf'"))
    session.rollback()
    with pytest.raises(DBAPIError):
        session.execute(text("DELETE FROM stored_blob"))  # arrastra una versión: se rechaza entero
    session.rollback()

    storage.delete_prepared("prepared/x/doc.pdf")  # el estado intermedio sí es descartable
    assert blobs(session) == ["documents/a/v1.pdf"]


def test_solo_se_descarta_lo_preparado(session):
    storage = DatabaseStorage(session)
    storage.save("documents/a/v1.pdf", PDF)
    session.commit()
    with pytest.raises(StorageError):
        storage.delete_prepared("documents/a/v1.pdf")
    assert blobs(session) == ["documents/a/v1.pdf"]


def test_atomicidad_con_la_transaccion(session):
    storage = DatabaseStorage(session)
    storage.save("documents/a/v1.pdf", PDF)
    session.rollback()  # la operación que lo creó se revirtió
    assert blobs(session) == []


# --- flujo completo con el almacén en la base -----------------------------------------------------------


@pytest.fixture
def in_db(client, settings, tmp_path):
    settings.storage_backend = "database"
    settings.storage_dir = str(tmp_path / "no-se-usa")
    return settings


def test_firma_local_con_los_pdf_en_la_base(client, in_db, session):
    signed = sign_fully(client)
    document_id = signed["document_id"]
    refs = blobs(session)
    assert len(refs) == 2 and all(r.startswith(f"documents/{document_id}/") for r in refs)  # sin prepared/
    assert not Path(in_db.storage_dir).exists()  # nada en disco

    download = client.get(f"/api/v1/documents/{document_id}/versions/2/download")
    assert download.status_code == 200 and download.content.startswith(b"%PDF-")
    verify = client.post(f"/api/v1/documents/{document_id}/verify").json()
    assert verify["valid"] is True and verify["hash_matches"] is True


def test_binario_y_version_van_juntos(client, in_db, session):
    document_id = sign_fully(client)["document_id"]
    session.expire_all()
    versions = session.scalars(select(DocumentVersion).where(DocumentVersion.document_id == uuid.UUID(document_id))).all()
    assert {v.storage_ref for v in versions} == set(blobs(session))


def test_token_con_los_pdf_en_la_base(client, in_db, token_env, pki, session):
    agent = AgentSimulator(signer_identity(pki))
    _rid, r = run_token_flow(client, agent)
    assert r.status_code == 200
    assert client.post(f"/api/v1/documents/{r.json()['document_id']}/verify").json()["valid"] is True
    assert not [b for b in blobs(session) if b.startswith("prepared/")]


def test_lote_con_los_pdf_en_la_base(client, in_db, session):
    created = create_batch(client, 3).json()
    client.post(f"/api/v1/signature-batches/{created['id']}/prepare", json={})
    done = client.post(f"/api/v1/signature-batches/{created['id']}/complete", json={}).json()
    assert done["status"] == "completed"
    assert len(blobs(session)) == 6
    for item in done["requests"]:
        assert client.get(item["download_url"].replace("http://test", "")).status_code == 200


def test_firma_remota_con_los_pdf_en_la_base(client, in_db, firmar_env, session):  # noqa: F811
    rid, op = prepared(client)
    assert approve(client, op).status_code == 200
    result = client.get(f"/api/v1/signature-requests/{rid}").json()
    assert result["status"] == "signed"
    assert client.post(f"/api/v1/documents/{result['document_id']}/verify").json()["valid"] is True


def test_widget_con_los_pdf_en_la_base(client, in_db, session):
    from fastapi.testclient import TestClient

    from firmadoc.main import app

    created = create(client, provider="local").json()
    token = created["signing_url"].partition("#t=")[2]
    headers = {"Authorization": f"Bearer {token}"}
    anon = TestClient(app)
    base = f"/api/v1/widget/requests/{created['id']}"
    assert anon.post(f"{base}/prepare", json={}, headers=headers).status_code == 200
    assert anon.post(f"{base}/complete", json={"signatures": []}, headers=headers).status_code == 200
    pdf = anon.get(f"{base}/download", headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")


# --- migración entre almacenes ----------------------------------------------------------------------------


def only_demo(report) -> bool:
    """Los únicos problemas son las versiones de demostración sin binario del fixture."""
    return all(p.startswith("demo/") for p in report.problems)


def signed_with_files(client, settings, n=2) -> list[str]:
    assert settings.storage_backend == "files"
    return [sign_fully(client)["document_id"] for _ in range(n)]


def test_archivos_a_base_completo_y_repetible(client, settings, session):
    documents = signed_with_files(client, settings)
    before = [client.post(f"/api/v1/documents/{d}/verify").json() for d in documents]
    assert all(v["valid"] for v in before)

    report = migrate(session, "files-to-database", settings.storage_dir)
    assert report.copied == 4  # 2 documentos × 2 versiones
    assert only_demo(report)  # el documento de demostración del fixture no tiene binario
    settings.storage_backend = "database"
    after = [client.post(f"/api/v1/documents/{d}/verify").json() for d in documents]
    assert [a["valid"] for a in after] == [True, True]
    assert all(a["hash_matches"] for a in after)

    again = migrate(session, "files-to-database", settings.storage_dir)
    assert again.copied == 0 and again.skipped == 4 and only_demo(again)
    assert Path(settings.storage_dir).exists()  # el origen no se borra


def test_archivo_corrupto_o_ausente_se_informa(client, settings, session):
    documents = signed_with_files(client, settings)
    files = sorted(Path(settings.storage_dir).rglob("v2-*.pdf"))
    files[0].write_bytes(files[0].read_bytes() + b"corrupcion")
    files[1].unlink()
    report = migrate(session, "files-to-database", settings.storage_dir)
    real = [p for p in report.problems if not p.startswith("demo/")]
    assert len(real) == 2 and report.copied == 2
    assert any("hash" in p for p in real) and any("no se pudo leer" in p for p in real)
    assert documents


def test_conflicto_si_el_destino_ya_tiene_otro_contenido(client, settings, session):
    signed_with_files(client, settings, n=1)
    ref = session.scalars(select(DocumentVersion.storage_ref).where(DocumentVersion.storage_ref.like("documents/%"))).first()
    DatabaseStorage(session).save(ref, b"otro contenido")
    session.commit()
    report = migrate(session, "files-to-database", settings.storage_dir)
    assert any("conflicto" in p for p in report.problems)


def test_base_a_archivos(client, settings, session, tmp_path):
    documents = signed_with_files(client, settings, n=1)
    migrate(session, "files-to-database", settings.storage_dir)
    target = tmp_path / "restaurado"
    report = migrate(session, "database-to-files", str(target))
    assert only_demo(report) and report.copied == 2
    originals = sorted(Path(settings.storage_dir).rglob("*.pdf"))
    for original in originals:
        restored = target / original.relative_to(settings.storage_dir)
        assert restored.read_bytes() == original.read_bytes()
    assert migrate(session, "database-to-files", str(target)).skipped == 2
    assert documents


def test_cli(client, settings, session, monkeypatch, capsys):
    from firmadoc import storage_migrate

    signed_with_files(client, settings, n=1)
    monkeypatch.setattr(storage_migrate, "get_settings", lambda: settings)
    monkeypatch.setattr(storage_migrate, "make_engine", lambda url: session.get_bind())
    assert storage_migrate.main(["files-to-database"]) == 1  # hay problemas: los binarios de demostración no existen
    assert "copiados: 2" in capsys.readouterr().out


# --- migración de Alembic ----------------------------------------------------------------------------------


def test_migracion_0006_reversible(db_url):
    cfg = alembic_config(db_url)
    command.upgrade(cfg, "0005")
    engine = make_engine(db_url)
    assert "stored_blob" not in inspect(engine).get_table_names()
    command.upgrade(cfg, "0006")
    assert "stored_blob" in inspect(engine).get_table_names()
    command.downgrade(cfg, "0005")
    assert "stored_blob" not in inspect(engine).get_table_names()
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(StoredBlob)).scalar() == 0
    engine.dispose()
