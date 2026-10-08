"""Elección del método de firma: proveedores permitidos por solicitud y selección desde el widget."""

import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select

from firmadoc.db import make_engine
from firmadoc.main import app
from firmadoc.models import AuditEvent, Provider, SignatureRequest

from .conftest import alembic_config
from .test_flow import create

WIDGET = "/api/v1/widget/requests"


@pytest.fixture
def anon(client):
    return TestClient(app)


def new(client, provider="token", allowed=None):
    extra = {} if allowed is None else {"allowed_providers": allowed}
    return create(client, provider=provider, **extra)


def widget(response):
    body = response.json()
    _base, _, token = body["signing_url"].partition("#t=")
    return body["id"], {"Authorization": f"Bearer {token}"}


# --- creación -----------------------------------------------------------------------------------------


def test_varios_metodos(client, session):
    r = new(client, "token", ["token", "local"])
    assert r.status_code == 201, r.text
    session.expire_all()
    assert session.get(SignatureRequest, uuid.UUID(r.json()["id"])).allowed_providers == "token,local"


def test_sin_lista_solo_el_proveedor(client, session):
    r = new(client, "local")
    session.expire_all()
    assert session.get(SignatureRequest, uuid.UUID(r.json()["id"])).allowed_providers is None


@pytest.mark.parametrize(
    "allowed",
    [["local"], ["token", "token"], ["token", "inventado"], ["token", "firmar"], []],
)
def test_listas_invalidas(client, session, allowed):
    before = session.scalar(select(func.count()).select_from(SignatureRequest))
    r = new(client, "token", allowed)
    assert r.status_code == 422, r.text
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(SignatureRequest)) == before


def test_firmar_habilitado_se_acepta(client, settings):
    settings.firmar_base_url = "http://test/mock/firmar"
    assert new(client, "token", ["token", "firmar"]).status_code == 201


# --- contexto -----------------------------------------------------------------------------------------


def test_contexto_informa_los_metodos(client, anon):
    rid, headers = widget(new(client, "token", ["token", "local"]))
    body = anon.get(f"{WIDGET}/{rid}", headers=headers).json()
    assert body["allowed_providers"] == ["token", "local"] and body["provider"] == "token"


def test_metodo_deshabilitado_despues_no_figura(client, anon, settings):
    settings.firmar_base_url = "http://test/mock/firmar"
    rid, headers = widget(new(client, "local", ["local", "firmar"]))
    assert anon.get(f"{WIDGET}/{rid}", headers=headers).json()["allowed_providers"] == ["local", "firmar"]
    settings.firmar_base_url = None
    assert anon.get(f"{WIDGET}/{rid}", headers=headers).json()["allowed_providers"] == ["local"]


# --- elección -----------------------------------------------------------------------------------------


def select_provider(anon, rid, headers, provider):
    return anon.post(f"{WIDGET}/{rid}/provider", json={"provider": provider}, headers=headers)


def test_cambio_de_metodo(client, anon, session):
    rid, headers = widget(new(client, "token", ["token", "local"]))
    r = select_provider(anon, rid, headers, "local")
    assert r.status_code == 200 and r.json()["provider"] == "local"
    session.expire_all()
    assert session.get(SignatureRequest, uuid.UUID(rid)).provider == Provider.LOCAL
    event = session.scalar(select(AuditEvent).where(AuditEvent.event_type == "provider_selected"))
    assert event.payload == {"from": "token", "to": "local"}
    # y el flujo posterior usa el método elegido: se firma de punta a punta con local
    assert anon.post(f"{WIDGET}/{rid}/prepare", json={}, headers=headers).status_code == 200
    done = anon.post(f"{WIDGET}/{rid}/complete", json={"signatures": []}, headers=headers)
    assert done.status_code == 200 and done.json()["status"] == "signed"


def test_mismo_metodo_no_registra_evento(client, anon, session):
    rid, headers = widget(new(client, "token", ["token", "local"]))
    assert select_provider(anon, rid, headers, "token").status_code == 200
    session.expire_all()
    count = session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == "provider_selected")
    )
    assert count == 0


def test_metodo_no_permitido(client, anon, session):
    rid, headers = widget(new(client, "token", ["token", "local"]))
    r = select_provider(anon, rid, headers, "firmar")
    assert r.status_code == 422 and r.json()["code"] == "provider_not_allowed"
    only_id, only_headers = widget(new(client, "token"))
    assert select_provider(anon, only_id, only_headers, "local").status_code == 422  # un solo método
    assert select_provider(anon, rid, headers, "inventado").status_code == 422
    session.expire_all()
    assert session.get(SignatureRequest, uuid.UUID(rid)).provider == Provider.TOKEN


@pytest.mark.parametrize("final", ["signing", "signed"])
def test_no_se_cambia_fuera_de_pending(client, anon, session, final):
    rid, headers = widget(new(client, "local", ["local", "token"]))
    anon.post(f"{WIDGET}/{rid}/prepare", json={}, headers=headers)
    if final == "signed":
        anon.post(f"{WIDGET}/{rid}/complete", json={"signatures": []}, headers=headers)
    assert select_provider(anon, rid, headers, "token").status_code == 409
    session.expire_all()
    assert session.get(SignatureRequest, uuid.UUID(rid)).provider == Provider.LOCAL


def test_sin_token_o_de_otra_solicitud(client, anon):
    rid, headers = widget(new(client, "token", ["token", "local"]))
    _other, other_headers = widget(new(client, "token", ["token", "local"]))
    assert anon.post(f"{WIDGET}/{rid}/provider", json={"provider": "local"}).status_code == 401
    assert anon.post(f"{WIDGET}/{rid}/provider", json={"provider": "local"}, headers=other_headers).status_code == 401
    assert anon.post(f"{WIDGET}/{rid}/provider", json={}, headers=headers).status_code == 422


def test_la_api_key_no_abre_la_ruta_del_widget(client):
    rid, _ = widget(new(client, "token", ["token", "local"]))
    r = client.post(f"{WIDGET}/{rid}/provider", json={"provider": "local"})  # solo X-API-Key
    assert r.status_code == 401


# --- migración ----------------------------------------------------------------------------------------


def test_migracion_0005_reversible(db_url):
    cfg = alembic_config(db_url)
    command.upgrade(cfg, "0004")
    engine = make_engine(db_url)

    def names() -> set[str]:
        return {c["name"] for c in inspect(engine).get_columns("signature_request")}

    assert "allowed_providers" not in names()
    command.upgrade(cfg, "0005")
    assert "allowed_providers" in names()
    command.downgrade(cfg, "0004")
    assert "allowed_providers" not in names()
    command.upgrade(cfg, "head")
    engine.dispose()
