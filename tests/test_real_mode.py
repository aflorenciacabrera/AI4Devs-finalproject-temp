"""Modo real: verificación previa, arranque seguro, sin proveedor local y sin seed de demostración."""

import pytest
from fastapi.testclient import TestClient

from firmadoc import preflight, seed
from firmadoc.api.deps import settings_dep
from firmadoc.config import Settings
from firmadoc.main import app
from firmadoc.models import IntegratingSystem

from .pdfs import make_pdf
from .test_flow import SIGNER, b64, create

SECRET = "secreto-real-de-mas-de-32-caracteres-xx"


@pytest.fixture
def good(settings, pki, tmp_path):
    """Configuración válida para el modo real (sobre la de pruebas)."""
    trust, crl = tmp_path / "trust", tmp_path / "crl"
    pki.write_anchors(trust)
    pki.write_crls(crl)
    settings.real_mode = True
    settings.signing_secret = SECRET
    settings.revocation_mode = "hard-fail"
    settings.revocation_fetch = False
    settings.trust_dir = str(trust)
    settings.crl_dir = str(crl)
    settings.webhook_worker_enabled = False
    return settings


def codes(settings, level=None) -> set[str]:
    return {f.code for f in preflight.check(settings) if level is None or f.level == level}


# --- verificación previa ---------------------------------------------------------------------------------


def test_por_defecto_no_es_modo_real():
    assert Settings().real_mode is False


def test_configuracion_correcta_no_tiene_errores(good):
    assert preflight.errors(preflight.check(good)) == []
    assert "local_disabled" in codes(good, "info")


def test_advertencias_no_impiden(good):
    warnings = codes(good, "warning")
    assert {"sqlite", "admin_disabled", "storage_files"} <= warnings
    assert preflight.errors(preflight.check(good)) == []


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"signing_secret": None}, "signing_secret_missing"),
        ({"revocation_mode": "soft-fail"}, "revocation_not_strict"),
        ({"revocation_mode": "off"}, "revocation_not_strict"),
        ({"firmar_mock_enabled": True}, "mock_enabled"),
        ({"webhook_allow_http": True}, "webhooks_unsafe"),
        ({"webhook_allow_private_hosts": True}, "webhooks_unsafe"),
    ],
)
def test_cada_error(good, change, code):
    for key, value in change.items():
        setattr(good, key, value)
    assert code in codes(good, "error")


def test_hard_fail_sin_fuente_de_revocacion(good, tmp_path):
    good.crl_dir = str(tmp_path / "vacio")
    assert "revocation_no_source" in codes(good, "error")
    good.revocation_fetch = True  # con consulta por red sí hay fuente
    assert "revocation_no_source" not in codes(good)


def test_sin_anclas(good, tmp_path):
    good.trust_dir = str(tmp_path / "sin-anclas")
    assert "no_trust_anchors" in codes(good, "error")


def test_varios_errores_juntos(good, tmp_path):
    good.signing_secret = None
    good.revocation_mode = "soft-fail"
    good.trust_dir = str(tmp_path / "nada")
    assert {"signing_secret_missing", "revocation_not_strict", "no_trust_anchors"} <= codes(good, "error")


def test_https_en_la_url_publica(good):
    good.public_base_url = "http://firmadoc.example.org"
    assert "public_url_not_https" in codes(good, "warning")
    good.public_base_url = "https://firmadoc.example.org"
    assert "public_url_not_https" not in codes(good)
    good.public_base_url = "http://localhost:8000"
    assert "public_url_not_https" not in codes(good)


def test_en_demostracion_los_hallazgos_son_advertencias(settings):
    settings.real_mode = False
    findings = preflight.check(settings)
    assert preflight.errors(findings) == []
    assert "signing_secret_missing" in {f.code for f in findings}  # se informa, pero no es error


def test_comando(good, monkeypatch, capsys):
    monkeypatch.setattr(preflight, "get_settings", lambda: good)
    assert preflight.main([]) == 0
    assert "Modo: REAL" in capsys.readouterr().out
    good.signing_secret = None
    assert preflight.main([]) == 1
    assert "signing_secret_missing" in capsys.readouterr().out


# --- arranque ---------------------------------------------------------------------------------------------------


def test_no_arranca_con_configuracion_insegura(good, tmp_path):
    good.signing_secret = None
    good.revocation_mode = "soft-fail"
    app.dependency_overrides[settings_dep] = lambda: good
    try:
        with pytest.raises(RuntimeError) as error, TestClient(app):
            pass
    finally:
        app.dependency_overrides.clear()
    message = str(error.value)
    assert "signing_secret_missing" in message and "revocation_not_strict" in message  # todos juntos


def test_arranca_con_configuracion_valida(good):
    app.dependency_overrides[settings_dep] = lambda: good
    try:
        with TestClient(app) as client:
            assert client.get("/health").json() == {"status": "ok"}
    finally:
        app.dependency_overrides.clear()


def test_demostracion_arranca_aunque_este_incompleta(settings):
    settings.webhook_worker_enabled = False
    app.dependency_overrides[settings_dep] = lambda: settings
    try:
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
    finally:
        app.dependency_overrides.clear()


# --- proveedores ------------------------------------------------------------------------------------------------


def request_body(provider, **extra):
    return {"document_base64": b64(make_pdf()), "signer": SIGNER, "provider": provider, **extra}


def test_local_no_esta_habilitado_en_modo_real(client, good):
    r = client.post("/api/v1/signature-requests", json=request_body("local"))
    assert r.status_code == 422 and "no está habilitado en modo real" in r.json()["detail"]
    nested = client.post("/api/v1/signature-requests", json=request_body("token", allowed_providers=["token", "local"]))
    assert nested.status_code == 422


def test_token_si_esta_habilitado_en_modo_real(client, good):
    assert client.post("/api/v1/signature-requests", json=request_body("token")).status_code == 201


def test_demostracion_sigue_igual(client, settings):
    assert create(client, provider="local").status_code == 201


# --- seed ---------------------------------------------------------------------------------------------------------


def test_seed_se_niega_en_modo_real(good, monkeypatch, session):
    monkeypatch.setattr(seed, "get_settings", lambda: good)
    with pytest.raises(SystemExit) as stop:
        seed.main()
    assert "modo real" in str(stop.value) and "integrators" in str(stop.value)
    session.expire_all()
    assert session.query(IntegratingSystem).count() == 0


def test_seed_funciona_fuera_del_modo_real(settings, monkeypatch, capsys):
    settings.real_mode = False
    monkeypatch.setattr(seed, "get_settings", lambda: settings)
    seed.main()
    assert "Seed aplicado" in capsys.readouterr().out
