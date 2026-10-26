"""Lotes en el widget: métodos elegibles, credencial y página del lote, endpoints, descarga y reintento."""

import base64
import hashlib
import io
import uuid
import zipfile

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from firmadoc.db import make_engine
from firmadoc.main import app
from firmadoc.models import SignatureBatch, SignatureRequest

from .agent_simulator import AgentSimulator
from .conftest import alembic_config
from .pdfs import make_pdf
from .test_flow import SIGNER, b64
from .test_signature_batches import counts, create_batch
from .test_token_flow import signer_identity

WIDGET = "/api/v1/widget/batches"


@pytest.fixture
def anon(client):
    """Cliente sin API key: lo que tiene el navegador."""
    return TestClient(app)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def new_batch(client, n=3, provider="local", **extra):
    body = create_batch(client, n, provider, **extra).json()
    token = body["signing_url"].partition("#t=")[2]
    return body, token


# --- métodos elegibles y URL del lote -----------------------------------------------------------------


def test_el_lote_devuelve_su_url_de_firma(client):
    body, token = new_batch(client)
    assert body["signing_url"] == f"http://test/sign/batch/{body['id']}#t={token}"


def test_metodos_permitidos_del_lote(client, session):
    body, _ = new_batch(client, provider="token", allowed_providers=["token", "local"])
    session.expire_all()
    batch = session.get(SignatureBatch, uuid.UUID(body["id"]))
    assert batch.allowed_providers == "token,local"
    requests = session.scalars(select(SignatureRequest).where(SignatureRequest.batch_id == batch.id)).all()
    assert {r.allowed_providers for r in requests} == {"token,local"}


@pytest.mark.parametrize(
    ("provider", "allowed"), [("firmar", None), ("local", ["local", "firmar"]), ("token", ["local"])]
)
def test_lote_con_metodos_invalidos_no_crea_nada(client, session, provider, allowed):
    before = counts(session)
    extra = {} if allowed is None else {"allowed_providers": allowed}
    assert create_batch(client, 2, provider, **extra).status_code == 422
    assert counts(session) == before


def test_sin_metodos_permitidos_vale_solo_el_del_lote(client, session):
    body, _ = new_batch(client)
    session.expire_all()
    assert session.get(SignatureBatch, uuid.UUID(body["id"])).allowed_providers is None


# --- migración -----------------------------------------------------------------------------------------


def test_migracion_0007_reversible(db_url):
    cfg = alembic_config(db_url)
    command.upgrade(cfg, "0006")
    engine = make_engine(db_url)
    columns = lambda: {c["name"] for c in inspect(engine).get_columns("signature_batch")}
    assert "allowed_providers" not in columns()
    command.upgrade(cfg, "0007")
    assert "allowed_providers" in columns()
    command.downgrade(cfg, "0006")
    assert "allowed_providers" not in columns()
    command.upgrade(cfg, "head")
    engine.dispose()


# --- página, credencial y seguridad --------------------------------------------------------------------


@pytest.fixture
def dist(settings, tmp_path):
    root = tmp_path / "widget-dist"
    root.mkdir()
    (root / "index.html").write_text("<!doctype html><title>Firmadoc</title>")
    settings.widget_dist = str(root)
    return root


def test_pagina_del_lote(client, anon, dist):
    body, _ = new_batch(client)
    r = anon.get(f"/sign/batch/{body['id']}")
    assert r.status_code == 200 and "frame-ancestors http://localhost:4200" in r.headers["content-security-policy"]
    missing = anon.get(f"/sign/batch/{uuid.uuid4()}")
    assert missing.status_code == 404 and "content-security-policy" not in missing.headers


def test_contexto_del_lote_sin_binarios(client, anon):
    body, token = new_batch(client)
    r = anon.get(f"{WIDGET}/{body['id']}", headers=bearer(token))
    assert r.status_code == 200
    ctx = r.json()
    assert set(ctx) == {
        "id", "status", "provider", "allowed_providers", "signer_name", "allowed_origins", "agent_url",
        "token_expires_at", "completed_at", "documents",
    }
    assert ctx["status"] == "pending" and len(ctx["documents"]) == 3
    item = ctx["documents"][0]
    assert item["document_name"].endswith(".pdf") and item["page_count"] == 1 and item["size_bytes"] > 0
    assert item["status"] == "pending" and item["version_number"] is None and item["error"] is None
    assert token not in r.text and "base64" not in r.text


def test_token_cruzado_entre_lote_y_solicitud(client, anon):
    body, token = new_batch(client)
    other, _ = new_batch(client)
    single = client.post(
        "/api/v1/signature-requests",
        json={"document_base64": b64(make_pdf()), "signer": SIGNER, "provider": "local"},
    ).json()
    single_token = single["signing_url"].partition("#t=")[2]
    for url, tok in [
        (f"{WIDGET}/{body['id']}", single_token),  # token de solicitud en un lote
        (f"{WIDGET}/{other['id']}", token),  # token de otro lote
        (f"/api/v1/widget/requests/{single['id']}", token),  # token de lote en una solicitud
    ]:
        r = anon.get(url, headers=bearer(tok))
        assert r.status_code == 401 and r.json()["code"] == "invalid_token"


@pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer x.y", "Basic abc"])
def test_sin_credenciales_validas(client, anon, header):
    body, token = new_batch(client)
    headers = {} if header is None else {"Authorization": header}
    assert anon.get(f"{WIDGET}/{body['id']}", headers=headers).status_code == 401
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    assert anon.get(f"{WIDGET}/{body['id']}", headers=bearer(tampered)).status_code == 401


def test_token_vencido(client, anon, settings):
    settings.signing_token_ttl_seconds = -1
    body, token = new_batch(client)
    assert anon.get(f"{WIDGET}/{body['id']}", headers=bearer(token)).status_code == 401


def test_la_api_key_no_abre_los_endpoints_del_widget_de_lote(client):
    body, _ = new_batch(client)
    assert client.get(f"{WIDGET}/{body['id']}").status_code == 401  # el cliente lleva solo la API key


def test_el_token_del_widget_no_abre_la_api_de_integracion_de_lotes(client, anon):
    body, token = new_batch(client)
    assert anon.get(f"/api/v1/signature-batches/{body['id']}", headers=bearer(token)).status_code == 401


# --- elección de método ---------------------------------------------------------------------------------


def test_elegir_metodo_del_lote(client, anon, session):
    body, token = new_batch(client, provider="token", allowed_providers=["token", "local"])
    url = f"{WIDGET}/{body['id']}"
    ctx = anon.get(url, headers=bearer(token)).json()
    assert ctx["allowed_providers"] == ["token", "local"]
    r = anon.post(f"{url}/provider", json={"provider": "local"}, headers=bearer(token))
    assert r.status_code == 200 and r.json()["provider"] == "local"
    session.expire_all()
    requests = session.scalars(select(SignatureRequest).where(SignatureRequest.batch_id == uuid.UUID(body["id"]))).all()
    assert {r.provider.value for r in requests} == {"local"}
    assert anon.post(f"{url}/provider", json={"provider": "firmar"}, headers=bearer(token)).status_code == 422


def test_no_se_cambia_el_metodo_con_el_lote_preparado(client, anon):
    body, token = new_batch(client, provider="token", allowed_providers=["token", "local"])
    url = f"{WIDGET}/{body['id']}"
    anon.post(f"{url}/provider", json={"provider": "local"}, headers=bearer(token))
    assert anon.post(f"{url}/prepare", json={}, headers={**bearer(token), "X-Session-Ref": "s1"}).status_code == 200
    r = anon.post(f"{url}/provider", json={"provider": "token"}, headers=bearer(token))
    assert r.status_code == 409


# --- flujo local, descarga y reintento -------------------------------------------------------------------


def sign_local_batch(anon, body, token):
    url = f"{WIDGET}/{body['id']}"
    h = {**bearer(token), "X-Session-Ref": "s1"}
    assert anon.post(f"{url}/prepare", json={}, headers=h).status_code == 200
    r = anon.post(f"{url}/complete", json={"signatures": []}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_flujo_local_completo_y_zip(client, anon):
    body, token = new_batch(client)
    ctx = sign_local_batch(anon, body, token)
    assert ctx["status"] == "completed"
    assert [d["status"] for d in ctx["documents"]] == ["signed"] * 3
    assert all(d["version_number"] == 2 for d in ctx["documents"])
    r = anon.get(f"{WIDGET}/{body['id']}/download", headers=bearer(token))
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert r.headers["cache-control"] == "no-store"
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert len(names) == 3 and len(set(names)) == 3 and all(n.endswith(".pdf") for n in names)
    assert not any("-v2" in n for n in names)  # nombres originales, sin sufijo de version


def test_el_zip_usa_los_nombres_originales_y_numera_los_repetidos(client, anon):
    """FIRDOC-53: cada PDF con el nombre con que se cargo; dos iguales se distinguen con -2."""
    documents = [
        {"document_base64": b64(make_pdf()), "external_document_id": "acta"},
        {"document_base64": b64(make_pdf()), "external_document_id": "acta"},
        {"document_base64": b64(make_pdf()), "external_document_id": "anexo.pdf"},
    ]
    body, token = new_batch(client, documents=documents)
    sign_local_batch(anon, body, token)
    r = anon.get(f"{WIDGET}/{body['id']}/download", headers=bearer(token))
    assert r.status_code == 200
    assert sorted(zipfile.ZipFile(io.BytesIO(r.content)).namelist()) == ["acta-2.pdf", "acta.pdf", "anexo.pdf"]


def test_descarga_sin_firmados(client, anon):
    body, token = new_batch(client)
    assert anon.get(f"{WIDGET}/{body['id']}/download", headers=bearer(token)).status_code == 409


def token_batch_via_widget(client, anon, pki, n=3):
    agent = AgentSimulator(signer_identity(pki))
    body, token = new_batch(client, n, provider="token")
    h = {**bearer(token), "X-Session-Ref": "s1"}
    url = f"{WIDGET}/{body['id']}"
    prepared = anon.post(f"{url}/prepare", json={"certificate_pem": agent.certificate_pem}, headers=h)
    assert prepared.status_code == 200, prepared.text
    return agent, body, token, h, url, prepared.json()["challenges"]


def test_exito_parcial_zip_solo_firmados_y_reintento(client, anon, session, token_env, pki):
    agent, _, token, h, url, challenges = token_batch_via_widget(client, anon, pki)
    signatures = [
        {"challenge_id": c["challenge_id"], "signature_base64": agent.sign(c["hash_to_sign"])} for c in challenges
    ]
    signatures[1]["signature_base64"] = agent.sign(base64.b64encode(hashlib.sha256(b"otro").digest()).decode())
    r = anon.post(f"{url}/complete", json={"signatures": signatures}, headers=h)
    assert r.status_code == 200, r.text
    ctx = r.json()
    assert ctx["status"] == "partial_failure"
    failed = [d for d in ctx["documents"] if d["status"] == "failed"]
    assert len(failed) == 1 and failed[0]["error"]["http_status"] == 422

    zipped = anon.get(f"{url}/download", headers=bearer(token))
    assert len(zipfile.ZipFile(io.BytesIO(zipped.content)).namelist()) == 2  # solo los firmados

    retried = anon.post(f"{url}/retry", headers=bearer(token))
    assert retried.status_code == 201, retried.text
    new_id = retried.json()["id"]
    new_token = retried.json()["signing_url"].partition("#t=")[2]
    assert retried.json()["signing_url"].startswith(f"http://test/sign/batch/{new_id}#t=")
    new_ctx = anon.get(f"{WIDGET}/{new_id}", headers=bearer(new_token)).json()
    assert [d["document_id"] for d in new_ctx["documents"]] == [failed[0]["document_id"]]  # los firmados no entran
    assert new_ctx["status"] == "pending" and new_ctx["provider"] == "token"
    assert anon.get(f"{WIDGET}/{new_id}", headers=bearer(token)).status_code == 401  # el token anterior no abre el nuevo


def test_reintento_sin_fallidos_o_sin_terminar(client, anon):
    body, token = new_batch(client)
    assert anon.post(f"{WIDGET}/{body['id']}/retry", headers=bearer(token)).status_code == 409  # sin terminar
    sign_local_batch(anon, body, token)
    assert anon.post(f"{WIDGET}/{body['id']}/retry", headers=bearer(token)).status_code == 409  # sin fallidos


def test_certificado_invalido_en_el_lote(client, anon, token_env, pki):
    body, token = new_batch(client, provider="token")
    r = anon.post(
        f"{WIDGET}/{body['id']}/prepare",
        json={"certificate_pem": "-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----"},
        headers={**bearer(token), "X-Session-Ref": "s1"},
    )
    assert r.status_code in (400, 422)
