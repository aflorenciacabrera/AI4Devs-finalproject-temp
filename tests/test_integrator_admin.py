"""Gestión de integradores desde el panel: alta, orígenes, rotación de claves, deshabilitar y auditoría."""

import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from firmadoc.db import make_engine
from firmadoc.main import app
from firmadoc.models import AdminEvent, IntegratingSystem
from firmadoc.services.panel_upload import PANEL_SYSTEM_NAME

from .conftest import alembic_config
from .pdfs import make_pdf
from .test_flow import SIGNER, b64

TOKEN = "t0ken-de-administracion-" + "x" * 20
URL = "/api/v1/admin/integrators"


@pytest.fixture
def admin(client, settings):
    settings.admin_token = TOKEN
    return {"Authorization": f"Bearer {TOKEN}"}


def new(client, admin, name="Gestor documental", origins=("https://gestor.example.org",)):
    r = client.post(URL, headers=admin, json={"name": name, "allowed_origins": list(origins)})
    assert r.status_code == 201, r.text
    return r.json()


def events(session) -> list[AdminEvent]:
    session.expire_all()
    return list(session.scalars(select(AdminEvent).order_by(AdminEvent.created_at)))


def can_authenticate(api_key: str) -> bool:
    """¿Esa API key abre la API de integradores? (cliente sin la API key de demostración)"""
    body = {"document_base64": b64(make_pdf()), "signer": SIGNER, "provider": "local"}
    r = TestClient(app).post("/api/v1/signature-requests", json=body, headers={"X-API-Key": api_key})
    assert r.status_code in (201, 401), r.text
    return r.status_code == 201


# --- alta y listado --------------------------------------------------------------------------------


def test_alta_con_credenciales_de_una_sola_vez(client, admin, session):
    created = new(client, admin)
    assert created["api_key"].startswith("fdk_") and created["webhook_secret"].startswith("whsec_")
    assert created["allowed_origins"] == ["https://gestor.example.org"] and created["status"] == "active"
    assert can_authenticate(created["api_key"])

    listed = client.get(URL, headers=admin).json()
    mine = next(i for i in listed if i["id"] == created["id"])
    assert "api_key" not in mine and "webhook_secret" not in mine and "api_key_hash" not in mine
    assert mine["has_webhook_secret"] is True
    assert created["api_key"] not in str(listed) and created["webhook_secret"] not in str(listed)

    session.expire_all()
    stored = session.get(IntegratingSystem, uuid.UUID(created["id"]))
    assert stored.api_key_hash != created["api_key"] and len(stored.api_key_hash) == 64  # solo el hash


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "allowed_origins": []},
        {"name": "X", "allowed_origins": ["gestor.example.org"]},
        {"name": "X", "allowed_origins": ["https://a.example.org/ruta"]},
        {"name": "X", "allowed_origins": ["javascript:alert(1)"]},
        {"name": PANEL_SYSTEM_NAME, "allowed_origins": []},
        {"name": "  " + PANEL_SYSTEM_NAME, "allowed_origins": []},
    ],
)
def test_validaciones_no_crean_nada(client, admin, session, payload):
    before = len(list(session.scalars(select(IntegratingSystem))))
    assert client.post(URL, headers=admin, json=payload).status_code == 422
    session.expire_all()
    assert len(list(session.scalars(select(IntegratingSystem)))) == before
    assert events(session) == []


def test_nombre_duplicado(client, admin):
    new(client, admin, "Repetido")
    assert client.post(URL, headers=admin, json={"name": "Repetido", "allowed_origins": []}).status_code == 422


def test_el_listado_muestra_el_sistema_de_demostracion_y_marca_el_interno(client, admin):
    client.post(
        "/api/v1/admin/signing-uploads", headers=admin, json={"filename": "a.pdf", "document_base64": b64(make_pdf())}
    )
    listed = {i["name"]: i for i in client.get(URL, headers=admin).json()}
    assert listed[PANEL_SYSTEM_NAME]["internal"] is True
    assert any(not i["internal"] for i in listed.values())


def test_sin_credenciales(client, admin, settings):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={"name": "x"}).status_code == 401
    settings.admin_token = None
    assert client.get(URL, headers=admin).status_code == 404


# --- cambios ---------------------------------------------------------------------------------------


def test_editar_los_origenes(client, admin, session):
    created = new(client, admin)
    r = client.patch(f"{URL}/{created['id']}", headers=admin, json={"allowed_origins": ["https://a.example.org", "https://b.example.org:8443"]})
    assert r.status_code == 200 and r.json()["allowed_origins"] == ["https://a.example.org", "https://b.example.org:8443"]
    bad = client.patch(f"{URL}/{created['id']}", headers=admin, json={"allowed_origins": ["http//x"]})
    assert bad.status_code == 422
    assert client.get(URL, headers=admin).json()[0] is not None
    changed = [e for e in events(session) if e.action == "integrator_origins_changed"]
    assert len(changed) == 1 and changed[0].detail["to"] == "https://a.example.org,https://b.example.org:8443"


def test_rotar_el_secreto_de_webhook(client, admin, session):
    created = new(client, admin)
    r = client.post(f"{URL}/{created['id']}/rotate-webhook-secret", headers=admin)
    assert r.status_code == 200 and r.json()["webhook_secret"].startswith("whsec_")
    assert r.json()["webhook_secret"] != created["webhook_secret"]
    session.expire_all()
    assert session.get(IntegratingSystem, uuid.UUID(created["id"])).webhook_secret == r.json()["webhook_secret"]
    event = next(e for e in events(session) if e.action == "integrator_webhook_secret_rotated")
    assert r.json()["webhook_secret"] not in str(event.detail) and created["webhook_secret"] not in str(event.detail)


def test_rotar_la_api_key_invalida_la_anterior(client, admin, session):
    created = new(client, admin)
    assert can_authenticate(created["api_key"])
    r = client.post(f"{URL}/{created['id']}/rotate-api-key", headers=admin)
    assert r.status_code == 200
    new_key = r.json()["api_key"]
    assert new_key != created["api_key"]
    assert not can_authenticate(created["api_key"]) and can_authenticate(new_key)
    event = next(e for e in events(session) if e.action == "integrator_api_key_rotated")
    assert new_key not in str(event.detail)


def test_deshabilitar_y_habilitar(client, admin):
    created = new(client, admin)
    r = client.post(f"{URL}/{created['id']}/disable", headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "disabled"
    assert not can_authenticate(created["api_key"])
    # mismo mensaje que una clave inválida: no revela la causa
    body = {"document_base64": b64(make_pdf()), "signer": SIGNER, "provider": "local"}
    off = TestClient(app).post("/api/v1/signature-requests", json=body, headers={"X-API-Key": created["api_key"]})
    bad = TestClient(app).post("/api/v1/signature-requests", json=body, headers={"X-API-Key": "fdk_inexistente"})
    assert off.json() == bad.json()
    assert client.post(f"{URL}/{created['id']}/enable", headers=admin).json()["status"] == "active"
    assert can_authenticate(created["api_key"])


def test_los_enlaces_del_widget_ya_emitidos_siguen_hasta_vencer(client, admin):
    created = new(client, admin)
    request = TestClient(app).post(
        "/api/v1/signature-requests",
        json={"document_base64": b64(make_pdf()), "signer": SIGNER, "provider": "local"},
        headers={"X-API-Key": created["api_key"]},
    ).json()
    token = request["signing_url"].partition("#t=")[2]
    client.post(f"{URL}/{created['id']}/disable", headers=admin)
    ctx = TestClient(app).get(f"/api/v1/widget/requests/{request['id']}", headers={"Authorization": f"Bearer {token}"})
    assert ctx.status_code == 200


def test_integrador_inexistente(client, admin):
    ghost = uuid.uuid4()
    assert client.patch(f"{URL}/{ghost}", headers=admin, json={"allowed_origins": []}).status_code == 404
    for action in ("rotate-webhook-secret", "rotate-api-key", "disable", "enable"):
        assert client.post(f"{URL}/{ghost}/{action}", headers=admin).status_code == 404


# --- sistema interno ------------------------------------------------------------------------------


def test_el_sistema_interno_esta_protegido(client, admin, session):
    client.post(
        "/api/v1/admin/signing-uploads", headers=admin, json={"filename": "a.pdf", "document_base64": b64(make_pdf())}
    )
    internal = next(i for i in client.get(URL, headers=admin).json() if i["internal"])
    before = events(session)
    for action in ("rotate-webhook-secret", "rotate-api-key", "disable", "enable"):
        assert client.post(f"{URL}/{internal['id']}/{action}", headers=admin).status_code == 409
    assert client.patch(f"{URL}/{internal['id']}", headers=admin, json={"allowed_origins": []}).status_code == 409
    session.expire_all()
    assert session.get(IntegratingSystem, uuid.UUID(internal["id"])).disabled_at is None
    assert len(events(session)) == len(before)


# --- auditoría -------------------------------------------------------------------------------------


def test_cada_accion_queda_auditada_sin_secretos(client, admin, session):
    created = new(client, admin)
    rid = created["id"]
    client.patch(f"{URL}/{rid}", headers=admin, json={"allowed_origins": ["https://n.example.org"]})
    secret = client.post(f"{URL}/{rid}/rotate-webhook-secret", headers=admin).json()["webhook_secret"]
    key = client.post(f"{URL}/{rid}/rotate-api-key", headers=admin).json()["api_key"]
    client.post(f"{URL}/{rid}/disable", headers=admin)
    client.post(f"{URL}/{rid}/enable", headers=admin)
    actions = [e.action for e in events(session)]
    assert actions == [
        "integrator_created", "integrator_origins_changed", "integrator_webhook_secret_rotated",
        "integrator_api_key_rotated", "integrator_disabled", "integrator_enabled",
    ]
    dump = str([e.detail for e in events(session)])
    for secret_value in (created["api_key"], created["webhook_secret"], secret, key):
        assert secret_value not in dump


# --- migración -------------------------------------------------------------------------------------


def test_migracion_0008_reversible(db_url):
    cfg = alembic_config(db_url)
    command.upgrade(cfg, "0007")
    engine = make_engine(db_url)
    columns = lambda: {c["name"] for c in inspect(engine).get_columns("integrating_system")}
    assert "disabled_at" not in columns()
    command.upgrade(cfg, "0008")
    assert "disabled_at" in columns()
    command.downgrade(cfg, "0007")
    assert "disabled_at" not in columns()
    command.upgrade(cfg, "head")
    engine.dispose()
