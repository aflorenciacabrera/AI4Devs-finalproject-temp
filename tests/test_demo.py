"""Modo demostración: un comando que prepara y arranca Firmadoc para firmar sin token USB."""

import base64
import json
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from firmadoc import demo
from firmadoc.api.deps import settings_dep
from firmadoc.config import Settings
from firmadoc.main import app

from .pdfs import make_pdf


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    """`prepare` fija variables de entorno del proceso: se restauran al terminar cada prueba."""
    saved = dict(os.environ)
    monkeypatch.delenv("FIRMADOC_REAL_MODE", raising=False)
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture
def demo_dir(tmp_path):
    return tmp_path / "data" / "demo"


def tables(directory) -> set[str]:
    with sqlite3.connect(directory / "firmadoc-demo.db") as conn:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def count(directory, table: str) -> int:
    with sqlite3.connect(directory / "firmadoc-demo.db") as conn:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_primer_arranque_crea_esquema_seed_y_archivos(demo_dir):
    env = demo.prepare(demo_dir, 8123)
    assert env.created is True
    assert {"integrating_system", "document", "signature_request", "admin_event"} <= tables(demo_dir)
    assert count(demo_dir, "integrating_system") == 1
    assert count(demo_dir, "stored_blob") == 2  # los PDF del seed (v1 y v2) viven en la base
    assert not (demo_dir / "storage").exists()  # ningún PDF en disco
    assert (demo_dir / "local-cert").is_dir()
    assert env.public_base_url == "http://localhost:8123"
    assert env.migrated == 0
    assert os.environ["FIRMADOC_PUBLIC_BASE_URL"] == "http://localhost:8123"
    assert os.environ["FIRMADOC_DATABASE_URL"].endswith("firmadoc-demo.db")
    assert os.environ["FIRMADOC_STORAGE_BACKEND"] == "database"
    assert os.environ["FIRMADOC_REAL_MODE"] == "false"


def test_arranque_repetido_no_duplica_el_seed(demo_dir):
    demo.prepare(demo_dir)
    again = demo.prepare(demo_dir)
    assert again.created is False
    assert count(demo_dir, "integrating_system") == 1


def test_los_secretos_son_estables_y_suficientemente_largos(demo_dir):
    first = demo.prepare(demo_dir)
    second = demo.prepare(demo_dir)
    assert (first.admin_token, first.signing_secret) == (second.admin_token, second.signing_secret)
    assert len(first.admin_token) >= 32 and len(first.signing_secret) >= 32
    assert first.admin_token != first.signing_secret
    saved = json.loads((demo_dir / "demo.json").read_text(encoding="utf8"))
    assert saved["admin_token"] == first.admin_token


def test_un_secreto_demasiado_corto_se_regenera(demo_dir):
    demo_dir.mkdir(parents=True)
    (demo_dir / "demo.json").write_text(json.dumps({"admin_token": "corto", "signing_secret": "corto"}))
    env = demo.prepare(demo_dir)
    assert len(env.admin_token) >= 32


def test_reset_borra_y_recrea(demo_dir):
    demo.prepare(demo_dir)
    first = json.loads((demo_dir / "demo.json").read_text(encoding="utf8"))
    demo.reset(demo_dir)
    assert not demo_dir.exists()
    env = demo.prepare(demo_dir)
    assert env.created is True and env.admin_token != first["admin_token"]


def test_reset_solo_borra_una_carpeta_llamada_demo(tmp_path):
    other = tmp_path / "mis-datos"
    other.mkdir()
    (other / "importante.txt").write_text("no borrar")
    with pytest.raises(demo.DemoError, match="demo"):
        demo.reset(other)
    assert (other / "importante.txt").exists()


@pytest.mark.parametrize("value", ["true", "1", "TRUE", "yes"])
def test_se_niega_con_el_modo_real_activo_sin_tocar_nada(demo_dir, monkeypatch, value, capsys):
    monkeypatch.setenv("FIRMADOC_REAL_MODE", value)
    with pytest.raises(demo.DemoError, match="REAL_MODE"):
        demo.prepare(demo_dir)
    assert not demo_dir.exists()
    monkeypatch.setattr(demo, "default_directory", lambda: demo_dir)
    assert demo.main(["--prepare-only", "--reset"]) == 1
    assert "REAL_MODE" in capsys.readouterr().err
    assert not demo_dir.exists()


def test_la_guia_muestra_el_panel_el_token_y_firma_propia(demo_dir):
    env = demo.prepare(demo_dir, 8200)
    text = demo.guide(env)
    assert "http://localhost:8200/admin" in text and env.admin_token in text
    assert "Firma propia" in text and "firmadoc-demo-key" in text


def test_token_de_prueba_y_directorio_de_confianza(demo_dir):
    from cryptography.hazmat.primitives import hashes, serialization

    from firmadoc import demo_pki
    from firmadoc.certificate_validation import CertificateChecker
    from firmadoc.trust import load_trust_store

    env = demo.prepare(demo_dir, 8200)
    token_dir = demo_dir / "token"
    assert (token_dir / "ca.crt").is_file() and (token_dir / "firmante.pem").is_file()
    assert env.token_dir == token_dir
    pki = demo_pki.ensure_demo_pki(token_dir)
    assert "CUIL 20000000001" in pki.signer.subject.rfc4514_string()
    assert pki.signer.issuer == pki.ca.subject
    # confianza propia de la demo, sin tocar backend/trust
    trust_dir = demo_dir / "trust"
    assert os.environ["FIRMADOC_TRUST_DIR"] == str(trust_dir)
    assert (trust_dir / "demo-ca.crt").is_file()
    assert not (demo.ROOT / "backend" / "trust" / "demo-ca.crt").exists()
    checker = CertificateChecker(load_trust_store(trust_dir), revocation_mode="soft-fail", allow_fetching=False)
    validated = checker.validate(pki.signer.public_bytes(serialization.Encoding.DER), "20000000001")
    assert validated.cuil == "20000000001"
    # el firmante del panel es el del token de prueba
    assert os.environ["FIRMADOC_PANEL_SIGNER_IDENTIFIER"] == "20000000001"
    assert os.environ["FIRMADOC_PANEL_SIGNER_NAME"] == "Firmante de Prueba"
    # se reutiliza en el siguiente arranque
    fingerprint = pki.signer.fingerprint(hashes.SHA256())
    demo.prepare(demo_dir, 8200)
    assert demo_pki.ensure_demo_pki(token_dir).signer.fingerprint(hashes.SHA256()) == fingerprint


def test_la_guia_muestra_el_comando_del_agente_y_el_pin(demo_dir):
    env = demo.prepare(demo_dir, 8200)
    text = demo.guide(env)
    assert "firmadoc-agent run --software-token" in text
    assert "firmante.pem --origin http://localhost:8200" in text
    assert "PIN del token de prueba: 1234" in text
    assert "Firmante del panel: Firmante de Prueba (CUIL 20000000001)" in text and "token de prueba" in text


def test_la_guia_muestra_el_comando_del_agente_con_pkcs11_para_el_token_fisico(demo_dir):
    env = demo.prepare(demo_dir, 8200)
    text = demo.guide(env)
    assert (
        'python -m firmadoc_agent --config "%APPDATA%\\FirmadocAgent\\config.json" run --origin http://localhost:8200'
        in text
    )
    assert "El PIN es el del token" in text and "--cuil y --nombre" in text


def test_firmante_real_para_el_token_fisico(demo_dir):
    signer = demo.PanelSigner.from_args("Titular del Token", "20-12345678-9", None)
    env = demo.prepare(demo_dir, 8200, signer)
    assert env.panel_signer == demo.PanelSigner("Titular del Token", "20123456789", "20123456789@invalid", real=True)
    assert os.environ["FIRMADOC_PANEL_SIGNER_NAME"] == "Titular del Token"
    assert os.environ["FIRMADOC_PANEL_SIGNER_IDENTIFIER"] == "20123456789"
    assert os.environ["FIRMADOC_PANEL_SIGNER_EMAIL"] == "20123456789@invalid"
    text = demo.guide(env)
    assert "Firmante del panel: Titular del Token (CUIL 20123456789) — token físico" in text
    # el token de prueba y su AC se generan igual: el camino con token de software no cambia
    assert (demo_dir / "token" / "firmante.pem").is_file() and (demo_dir / "trust" / "demo-ca.crt").is_file()
    assert "firmadoc-agent run --software-token" in text


def test_firmante_real_con_correo_propio():
    signer = demo.PanelSigner.from_args("Titular", "20123456789", "titular@example.org")
    assert signer == demo.PanelSigner("Titular", "20123456789", "titular@example.org", real=True)


def test_sin_parametros_el_firmante_es_el_del_token_de_prueba(demo_dir):
    assert demo.PanelSigner.from_args(None, None, None) is None
    env = demo.prepare(demo_dir, 8200)
    assert env.signer is None and env.panel_signer.real is False
    assert os.environ["FIRMADOC_PANEL_SIGNER_IDENTIFIER"] == "20000000001"


@pytest.mark.parametrize(
    ("nombre", "cuil", "email", "falta"),
    [
        ("Titular", None, None, "--cuil"),
        (None, "20123456789", None, "--nombre"),
        ("  ", "20123456789", None, "--nombre"),
        ("Titular", "2012345678", None, "11 dígitos"),
        ("Titular", "20-12345678-9X", None, "11 dígitos"),
        (None, None, "x@example.org", "--email"),
    ],
)
def test_parametros_del_firmante_incompletos_o_invalidos(nombre, cuil, email, falta):
    with pytest.raises(demo.DemoError, match=falta):
        demo.PanelSigner.from_args(nombre, cuil, email)


def test_main_rechaza_un_firmante_invalido_sin_crear_nada(demo_dir, monkeypatch, capsys):
    monkeypatch.setattr(demo, "default_directory", lambda: demo_dir)
    assert demo.main(["--prepare-only", "--cuil", "123"]) == 1
    err = capsys.readouterr().err
    assert "--nombre" in err or "11 dígitos" in err
    assert not demo_dir.exists()


def test_main_con_cuil_y_nombre_configura_el_firmante_real(demo_dir, monkeypatch, capsys):
    monkeypatch.setattr(demo, "default_directory", lambda: demo_dir)
    assert demo.main(["--prepare-only", "--port", "8322", "--cuil", "20123456789", "--nombre", "Titular"]) == 0
    assert "Firmante del panel: Titular (CUIL 20123456789)" in capsys.readouterr().out
    assert os.environ["FIRMADOC_PANEL_SIGNER_IDENTIFIER"] == "20123456789"


def test_la_guia_muestra_el_panel_angular(demo_dir, monkeypatch, tmp_path):
    built = tmp_path / "browser"
    built.mkdir()
    (built / "index.html").write_text("<html></html>")
    monkeypatch.setattr(demo, "frontend_dist", lambda: built)
    env = demo.prepare(demo_dir, 8200)
    assert env.frontend_built is True
    assert "http://localhost:8200/panel" in demo.guide(env)
    assert os.environ["FIRMADOC_FRONTEND_DIST"] == str(built)


def test_avisa_si_el_panel_angular_no_esta_compilado(demo_dir, monkeypatch, tmp_path):
    monkeypatch.setattr(demo, "frontend_dist", lambda: tmp_path / "sin-compilar")
    env = demo.prepare(demo_dir)
    assert env.frontend_built is False
    assert "cd frontend && npm install && npm run build" in demo.guide(env)


def test_avisa_si_el_widget_no_esta_compilado(demo_dir, monkeypatch, tmp_path):
    monkeypatch.setattr(demo, "widget_dist", lambda: tmp_path / "sin-compilar")
    env = demo.prepare(demo_dir)
    assert env.widget_built is False
    assert "npm run build" in demo.guide(env)


def test_prepare_only_no_arranca_el_servidor(demo_dir, monkeypatch, capsys):
    monkeypatch.setattr(demo, "default_directory", lambda: demo_dir)
    assert demo.main(["--prepare-only", "--port", "8321"]) == 0
    assert "http://localhost:8321/admin" in capsys.readouterr().out


def test_la_guia_se_imprime_en_una_consola_cp1252_con_emoji_en_la_ruta(tmp_path, monkeypatch):
    import io
    import sys

    directory = tmp_path / "Proyecto 🚀" / "demo"
    monkeypatch.setattr(demo, "default_directory", lambda: directory)
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1252", write_through=True)
    monkeypatch.setattr(sys, "stdout", console)
    assert demo.main(["--prepare-only"]) == 0
    console.flush()
    assert "Firma propia" in raw.getvalue().decode("cp1252")


def sign_from_panel(env, storage_backend: str | None = None) -> dict:
    """Carga un PDF desde el panel y lo firma con «Firma propia» en el entorno que fijó `prepare`.

    Con `storage_backend="files"` simula un entorno anterior, cuando la demo guardaba los PDF en disco.
    """
    settings = Settings()  # lee las variables que fijó `prepare`
    if storage_backend:
        settings = settings.model_copy(update={"storage_backend": storage_backend})
    app.dependency_overrides[settings_dep] = lambda: settings
    try:
        client = TestClient(app)
        assert client.get("/health").status_code == 200
        assert client.get("/admin").status_code == 200
        admin = {"Authorization": f"Bearer {env.admin_token}"}
        r = client.post(
            "/api/v1/admin/signing-uploads",
            headers=admin,
            json={"filename": "Prueba.pdf", "document_base64": base64.b64encode(make_pdf()).decode()},
        )
        assert r.status_code == 201, r.text
        token = r.json()["signing_url"].partition("#t=")[2]
        rid = r.json()["request_id"]
        h = {"Authorization": f"Bearer {token}", "X-Session-Ref": "s1"}
        base = f"/api/v1/widget/requests/{rid}"
        assert client.post(f"{base}/provider", json={"provider": "local"}, headers=h).status_code == 200
        assert client.post(f"{base}/prepare", json={}, headers=h).status_code == 200
        done = client.post(f"{base}/complete", json={"signatures": []}, headers=h)
        assert done.status_code == 200, done.text
        assert done.json()["status"] == "signed" and done.json()["document"]["version_number"] == 2
        signed = client.get(f"{base}/download", headers=h)
        assert signed.status_code == 200 and signed.content.startswith(b"%PDF-")
        return {"document_id": r.json()["document_id"], "signed": signed.content}
    finally:
        app.dependency_overrides.clear()


def download_versions(env, document_id: str) -> list[bytes]:
    app.dependency_overrides[settings_dep] = lambda: Settings()
    try:
        client = TestClient(app)
        admin = {"Authorization": f"Bearer {env.admin_token}"}
        out = []
        for n in (1, 2):
            r = client.get(f"/api/v1/admin/documents/{document_id}/versions/{n}/download", headers=admin)
            assert r.status_code == 200, r.text
            out.append(r.content)
        return out
    finally:
        app.dependency_overrides.clear()


def test_el_entorno_preparado_permite_entrar_al_panel_y_firmar_con_firma_propia(demo_dir):
    env = demo.prepare(demo_dir)
    sign_from_panel(env)
    assert count(demo_dir, "stored_blob") == 4  # seed (2) + original y firmado del PDF cargado
    assert not (demo_dir / "storage").exists()  # nada en disco: ni versiones ni estado intermedio


def test_los_pdf_de_un_entorno_anterior_pasan_a_la_base(demo_dir):
    env = demo.prepare(demo_dir)
    legacy = sign_from_panel(env, storage_backend="files")  # entorno anterior: PDF en data/demo/storage
    files = sorted((demo_dir / "storage").rglob("*.pdf"))
    assert len(files) == 2 and count(demo_dir, "stored_blob") == 2

    again = demo.prepare(demo_dir)
    assert again.migrated == 2
    assert count(demo_dir, "stored_blob") == 4
    assert sorted((demo_dir / "storage").rglob("*.pdf")) == files  # no se borra nada
    assert "Se copiaron 2 PDF" in demo.guide(again)
    v1, v2 = download_versions(again, legacy["document_id"])
    assert v2 == legacy["signed"] and v1.startswith(b"%PDF-")

    third = demo.prepare(demo_dir)
    assert third.migrated == 0 and count(demo_dir, "stored_blob") == 4
    assert "Se copiaron" not in demo.guide(third)


def test_un_pdf_anterior_ausente_o_corrupto_impide_arrancar(demo_dir):
    env = demo.prepare(demo_dir)
    sign_from_panel(env, storage_backend="files")
    files = sorted((demo_dir / "storage").rglob("*.pdf"))
    files[0].write_bytes(files[0].read_bytes() + b"corrupcion")
    files[1].unlink()
    with pytest.raises(demo.DemoError) as e:
        demo.prepare(demo_dir)
    message = str(e.value)
    assert "2 PDF" in message and "--reset" in message
    assert "hash" in message and "no se pudo leer" in message
