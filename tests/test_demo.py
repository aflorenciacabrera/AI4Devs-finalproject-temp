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
    assert any((demo_dir / "storage").rglob("*.pdf"))  # el seed guarda sus PDF
    assert (demo_dir / "local-cert").is_dir()
    assert env.public_base_url == "http://localhost:8123"
    assert os.environ["FIRMADOC_PUBLIC_BASE_URL"] == "http://localhost:8123"
    assert os.environ["FIRMADOC_DATABASE_URL"].endswith("firmadoc-demo.db")
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


def test_el_entorno_preparado_permite_entrar_al_panel_y_firmar_con_firma_propia(demo_dir):
    env = demo.prepare(demo_dir)
    app.dependency_overrides[settings_dep] = lambda: Settings()  # lee las variables que fijó `prepare`
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
    finally:
        app.dependency_overrides.clear()
