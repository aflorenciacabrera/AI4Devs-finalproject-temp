"""Administración: acceso, historial, custodia, webhooks, anclas de confianza y certificado propio."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError

from firmadoc import integrators, trust
from firmadoc.config import Settings
from firmadoc.db import make_engine
from firmadoc.models import (
    AdminEvent,
    AuditEvent,
    DeliveryStatus,
    SignatureRequest,
    WebhookDelivery,
)

from .agent_simulator import AgentSimulator
from .conftest import alembic_config
from .test_flow import SIGNER, create, sign_fully
from .test_token_flow import run_token_flow, signer_identity

TOKEN = "t0ken-de-administracion-" + "x" * 20


@pytest.fixture
def admin(client, settings):
    settings.admin_token = TOKEN
    return {"Authorization": f"Bearer {TOKEN}"}


def get(client, admin, path, **params):
    return client.get(f"/api/v1/admin{path}", headers=admin, params=params)


def events(session) -> list[AdminEvent]:
    session.expire_all()
    return list(session.scalars(select(AdminEvent).order_by(AdminEvent.created_at)))


# --- acceso -------------------------------------------------------------------------------------------


def test_sin_token_configurado_no_existe(client, settings):
    assert settings.admin_token is None
    assert client.get("/api/v1/admin/events", headers={"Authorization": "Bearer lo-que-sea"}).status_code == 404
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/admin.js").status_code == 404


@pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer otro", "Basic " + TOKEN, TOKEN])
def test_credenciales_invalidas(client, admin, header):
    headers = {} if header is None else {"Authorization": header}
    assert client.get("/api/v1/admin/events", headers=headers).status_code == 401


def test_api_key_de_integrador_no_sirve(client, admin):
    from firmadoc.seed import DEMO_API_KEY

    r = client.get("/api/v1/admin/events", headers={"Authorization": f"Bearer {DEMO_API_KEY}"})
    assert r.status_code == 401
    assert client.get("/api/v1/admin/events", headers={"X-API-Key": DEMO_API_KEY}).status_code == 401


def test_el_token_de_administracion_no_abre_la_api_de_integradores(client, admin):
    r = client.get(f"/api/v1/signature-batches/{uuid.uuid4()}", headers={"X-API-Key": TOKEN})
    assert r.status_code == 401


def test_token_corto_se_rechaza():
    with pytest.raises(ValueError):
        Settings(admin_token="corto")
    assert Settings(admin_token="").admin_token is None


# --- historial ----------------------------------------------------------------------------------------


def test_listado_sin_filtros(client, admin):
    sign_fully(client)
    create(client)
    body = get(client, admin, "/signature-requests").json()
    assert body["total"] == 3 and len(body["items"]) == 3  # incluye la del seed
    dates = [i["created_at"] for i in body["items"]]
    assert dates == sorted(dates, reverse=True)
    item = next(i for i in body["items"] if i["status"] == "signed" and i["document"]["external_document_id"] == "exp-1/doc-1")
    assert item["document"]["signing_status"] == "signed" and item["document"]["current_version_number"] == 2
    assert item["integrating_system"]["name"] and item["signer"]["identifier"] == SIGNER["identifier"]
    assert item["certificate"]["serial_number"]


def test_filtros_combinados(client, admin, session):
    sign_fully(client)
    create(client)
    _system, key, _s = integrators.create(session, "Otro integrador", "")
    other = create(client.__class__(client.app, headers={"X-API-Key": key}), provider="local")
    assert other.status_code == 201
    assert get(client, admin, "/signature-requests", status="signed").json()["total"] == 2  # seed + la firmada
    assert get(client, admin, "/signature-requests", status="pending").json()["total"] == 2
    assert get(client, admin, "/signature-requests", provider="token").json()["total"] == 0
    systems = {i["integrating_system"]["id"] for i in get(client, admin, "/signature-requests").json()["items"]}
    assert len(systems) == 2
    one = get(client, admin, "/signature-requests", integrating_system_id=next(iter(systems))).json()
    assert 1 <= one["total"] <= 3
    now = datetime.now(UTC)
    window = get(client, admin, "/signature-requests", status="signed",
                 created_from=(now - timedelta(minutes=5)).isoformat(), created_to=(now + timedelta(minutes=5)).isoformat())
    assert window.json()["total"] >= 1
    future = get(client, admin, "/signature-requests", created_from=(now + timedelta(days=1)).isoformat())
    assert future.json()["total"] == 0


def test_filtro_por_firmante(client, admin):
    sign_fully(client)
    by_cuil = get(client, admin, "/signature-requests", signer=SIGNER["identifier"]).json()
    assert by_cuil["total"] == 1
    by_name = get(client, admin, "/signature-requests", signer="juan pÉr").json()  # sin distinguir mayúsculas
    assert by_name["total"] == 1
    assert get(client, admin, "/signature-requests", signer="%").json()["total"] == 0  # comodín literal
    assert get(client, admin, "/signature-requests", signer="_uan").json()["total"] == 0
    assert get(client, admin, "/signature-requests", signer="nadie").json()["total"] == 0


def test_paginacion(client, admin):
    for _ in range(4):
        create(client)
    first = get(client, admin, "/signature-requests", limit=2, offset=0).json()
    second = get(client, admin, "/signature-requests", limit=2, offset=2).json()
    last = get(client, admin, "/signature-requests", limit=2, offset=4).json()
    assert first["total"] == second["total"] == last["total"] == 5
    ids = [i["id"] for page in (first, second, last) for i in page["items"]]
    assert len(ids) == 5 and len(set(ids)) == 5


@pytest.mark.parametrize(
    "params",
    [{"limit": 201}, {"limit": 0}, {"offset": -1}, {"status": "inventado"}, {"provider": "x"}, {"integrating_system_id": "no-uuid"}],
)
def test_parametros_invalidos(client, admin, params):
    assert get(client, admin, "/signature-requests", **params).status_code == 422


# --- custodia -----------------------------------------------------------------------------------------


def test_custodia_de_un_documento_firmado_dos_veces(client, admin):
    document_id = sign_fully(client)["document_id"]
    again = client.post("/api/v1/signature-requests", json={"document_id": document_id, "signer": SIGNER, "provider": "local"}).json()
    client.post(f"/api/v1/signature-requests/{again['id']}/prepare", json={})
    client.post(f"/api/v1/signature-requests/{again['id']}/complete", json={})
    r = get(client, admin, f"/documents/{document_id}/custody")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [v["version_number"] for v in body["versions"]] == [1, 2, 3]
    assert [v["is_current"] for v in body["versions"]] == [False, False, True]
    assert len(body["signature_requests"]) == 2
    for request in body["signature_requests"]:
        kinds = {e["event_type"] for e in request["events"]}
        assert {"created", "prepared", "signed"} <= kinds
        assert len(request["challenges"]) == 1 and request["challenges"][0]["consumed_at"]


def test_custodia_sin_secretos(client, admin):
    document_id = sign_fully(client)["document_id"]
    raw = get(client, admin, f"/documents/{document_id}/custody").text
    assert "hash_to_sign" not in raw and "signed_document_base64" not in raw and '"body"' not in raw


def test_custodia_inexistente(client, admin):
    assert get(client, admin, f"/documents/{uuid.uuid4()}/custody").status_code == 404


# --- webhooks -----------------------------------------------------------------------------------------


def failed_delivery(client, session, monkeypatch) -> uuid.UUID:
    from firmadoc import webhooks

    monkeypatch.setattr(webhooks, "RESOLVER", lambda host, port: ["93.184.216.34"])
    sign_fully(client, callback_url="https://hooks.example.org/in")
    session.expire_all()
    delivery = session.scalar(select(WebhookDelivery))
    delivery.status, delivery.attempts, delivery.last_error = DeliveryStatus.FAILED, 6, "HTTP 500"
    delivery.next_attempt_at = None
    session.commit()
    return delivery.id


def test_listar_y_reenviar_entrega_fallida(client, admin, session, monkeypatch):
    delivery_id = failed_delivery(client, session, monkeypatch)
    listing = get(client, admin, "/webhook-deliveries", status="failed").json()
    assert listing["total"] == 1 and listing["items"][0]["last_error"] == "HTTP 500"
    assert "body" not in listing["items"][0]

    r = client.post(f"/api/v1/admin/webhook-deliveries/{delivery_id}/retry", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending" and r.json()["attempts"] == 0
    [event] = events(session)
    assert event.action == "webhook_retry" and event.detail["previous_attempts"] == 6
    assert client.post(f"/api/v1/admin/webhook-deliveries/{delivery_id}/retry", headers=admin).status_code == 409


def test_reenvio_inexistente(client, admin):
    assert client.post(f"/api/v1/admin/webhook-deliveries/{uuid.uuid4()}/retry", headers=admin).status_code == 404


def test_las_lecturas_no_generan_eventos(client, admin, session):
    sign_fully(client)
    for path in ("/signature-requests", "/webhook-deliveries", "/trust-anchors", "/local-certificate", "/events"):
        assert get(client, admin, path).status_code == 200
    assert events(session) == []


# --- anclas de confianza ------------------------------------------------------------------------------


@pytest.fixture
def own_trust(token_env, pki, tmp_path):
    """Directorio de anclas propio de la prueba (las pruebas modifican su contenido)."""
    directory = tmp_path / "trust-admin"
    pki.write_anchors(directory)
    token_env.trust_dir = str(directory)
    return directory


def test_listar_anclas(client, admin, own_trust):
    anchors = get(client, admin, "/trust-anchors").json()
    assert sorted(a["is_root"] for a in anchors) == [False, True]
    assert all(len(a["fingerprint"]) == 64 and a["subject"] for a in anchors)


def test_agregar_ancla_hace_confiable_una_cadena(client, admin, session, token_env, pki, tmp_path):
    empty = tmp_path / "vacio"
    empty.mkdir()
    token_env.trust_dir = str(empty)
    agent = AgentSimulator(signer_identity(pki))
    created = create(client, provider="token").json()
    rid = created["id"]

    def prepare():
        return client.post(f"/api/v1/signature-requests/{rid}/prepare", json={"certificate_pem": agent.certificate_pem})

    untrusted = prepare()
    assert untrusted.status_code == 422 and untrusted.json()["code"] == "certificate_untrusted"

    for authority in (pki.root, pki.ca):
        r = client.post("/api/v1/admin/trust-anchors", json={"certificate_pem": authority.pem.decode()}, headers=admin)
        assert r.status_code == 201, r.text
    assert prepare().status_code == 200
    assert [e.action for e in events(session)] == ["trust_anchor_added", "trust_anchor_added"]
    assert all(len(e.detail["fingerprint"]) == 64 for e in events(session))


def test_quitar_ancla_corta_la_confianza(client, admin, session, own_trust, pki):
    agent = AgentSimulator(signer_identity(pki))
    _rid, ok = run_token_flow(client, agent)
    assert ok.status_code == 200
    root = next(a for a in get(client, admin, "/trust-anchors").json() if a["is_root"])
    r = client.delete(f"/api/v1/admin/trust-anchors/{root['fingerprint']}", headers=admin)
    assert r.status_code == 200, r.text
    assert [a["is_root"] for a in get(client, admin, "/trust-anchors").json()] == [False]
    rid = create(client, provider="token").json()["id"]
    denied = client.post(f"/api/v1/signature-requests/{rid}/prepare", json={"certificate_pem": agent.certificate_pem})
    assert denied.status_code == 422 and denied.json()["code"] == "certificate_untrusted"
    assert events(session)[-1].action == "trust_anchor_removed"
    assert (  # lo ya firmado no cambia
        client.post(f"/api/v1/documents/{ok.json()['document_id']}/verify").json()["signatures"][0]["intact"] is True
    )


def test_ancla_duplicada_e_invalida(client, admin, session, own_trust, pki):
    post = lambda pem: client.post("/api/v1/admin/trust-anchors", json={"certificate_pem": pem}, headers=admin)
    assert post(pki.root.pem.decode()).status_code == 409
    assert post("no es un pem").status_code == 422
    assert post(pki.root.pem.decode() + pki.ca.pem.decode()).status_code == 422  # más de un certificado
    leaf = signer_identity(pki)
    assert post(leaf.pem).status_code == 422  # certificado final: no es CA ni autofirmado
    assert events(session) == []
    assert len(list(own_trust.iterdir())) == 2  # no se tocó el directorio


def test_ancla_vencida(client, admin, own_trust):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(65537, 2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Raiz vencida")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=30)).not_valid_after(now - timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    r = client.post("/api/v1/admin/trust-anchors", json={"certificate_pem": pem}, headers=admin)
    assert r.status_code == 422 and "vencido" in r.json()["detail"]


def test_quitar_ancla_inexistente_o_con_archivo_compartido(client, admin, own_trust, pki):
    assert client.delete("/api/v1/admin/trust-anchors/" + "0" * 64, headers=admin).status_code == 404
    assert client.delete("/api/v1/admin/trust-anchors/no-es-una-huella", headers=admin).status_code == 404
    bundle = own_trust / "bundle.pem"
    bundle.write_bytes(pki.other_root.pem + pki.other_ca.pem)
    trust._cached.cache_clear()
    other = next(a for a in get(client, admin, "/trust-anchors").json() if a["file"] == "bundle.pem")
    assert client.delete(f"/api/v1/admin/trust-anchors/{other['fingerprint']}", headers=admin).status_code == 409
    assert bundle.exists()


# --- certificado propio -------------------------------------------------------------------------------


def test_rotar_certificado_propio(client, admin, session, settings):
    before = sign_fully(client)
    old_document = before["document_id"]
    cert_dir = Path(settings.local_cert_dir)
    old_key = (cert_dir / "demo-signer.key").read_bytes()
    old_serial = get(client, admin, "/local-certificate").json()["current"]["serial_number"]

    r = client.post("/api/v1/admin/local-certificate/rotate", headers=admin)
    assert r.status_code == 200, r.text
    info = get(client, admin, "/local-certificate").json()
    assert info["current"]["serial_number"] != old_serial
    assert [c["serial_number"] for c in info["archived"]] == [old_serial]
    assert (cert_dir / "demo-signer.key").read_bytes() != old_key  # la clave vieja ya no existe
    assert not list((cert_dir / "archive").glob("*.key"))  # y no se archivó
    assert events(session)[-1].action == "local_certificate_rotated"

    # lo firmado antes sigue verificándose, y lo nuevo se firma con el certificado nuevo
    assert client.post(f"/api/v1/documents/{old_document}/verify").json()["valid"] is True
    after = sign_fully(client)
    assert client.get(f"/api/v1/documents/{after['document_id']}/signatures").json()[0]["certificate"]["serial_number"] != old_serial
    assert client.post(f"/api/v1/documents/{after['document_id']}/verify").json()["valid"] is True


def test_rotar_sin_certificado_previo(client, admin, session):
    assert get(client, admin, "/local-certificate").json() == {"current": None, "archived": []}
    r = client.post("/api/v1/admin/local-certificate/rotate", headers=admin)
    assert r.status_code == 200 and r.json()["archived_fingerprint"] is None
    assert get(client, admin, "/local-certificate").json()["archived"] == []


# --- eventos e inmutabilidad --------------------------------------------------------------------------


def test_listado_de_eventos(client, admin, session):
    client.post("/api/v1/admin/local-certificate/rotate", headers=admin)
    client.post("/api/v1/admin/local-certificate/rotate", headers=admin)
    body = get(client, admin, "/events", limit=1).json()
    assert body["total"] == 2 and len(body["items"]) == 1 and body["items"][0]["actor"] == "admin"


def test_admin_event_es_inmutable(session):
    session.add(AdminEvent(actor="admin", action="prueba", detail={}))
    session.commit()
    event = session.scalar(select(AdminEvent))
    with pytest.raises(DBAPIError):
        session.execute(update(AdminEvent).where(AdminEvent.id == event.id).values(action="otra"))
    session.rollback()
    with pytest.raises(DBAPIError):
        session.execute(text("DELETE FROM admin_event"))
    session.rollback()


def test_migracion_0003_reversible(db_url):
    cfg = alembic_config(db_url)
    command.upgrade(cfg, "0002")
    engine = make_engine(db_url)
    from sqlalchemy import inspect

    assert "admin_event" not in inspect(engine).get_table_names()
    command.upgrade(cfg, "0003")
    assert "admin_event" in inspect(engine).get_table_names()
    command.downgrade(cfg, "0002")
    assert "admin_event" not in inspect(engine).get_table_names()
    command.upgrade(cfg, "head")
    assert "admin_event" in inspect(engine).get_table_names()
    engine.dispose()


def test_solicitudes_no_se_modifican_al_listar(client, admin, session):
    sign_fully(client)
    before = session.scalar(select(SignatureRequest.id).limit(1))
    get(client, admin, "/signature-requests")
    assert session.scalar(select(SignatureRequest.id).limit(1)) == before
    assert session.scalar(select(AuditEvent.id).limit(1)) is not None


# --- página -------------------------------------------------------------------------------------------


def test_pagina_con_cabeceras_restrictivas(client, admin):
    r = client.get("/admin")
    assert r.status_code == 200 and "Administración" in r.text
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe-inline" not in csp
    assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"
    js = client.get("/admin/admin.js")
    assert js.status_code == 200 and js.headers["content-type"].startswith("text/javascript")
    assert client.get("/admin/admin.css").status_code == 200
    assert client.get("/admin/otro.js").status_code == 404
    assert client.get("/admin/..%2Fconfig.py").status_code == 404


def test_la_pagina_no_usa_innerhtml_ni_scripts_en_linea(client, admin):
    html = client.get("/admin").text
    assert "<script>" not in html and " onclick=" not in html and "style=" not in html
    source = client.get("/admin/admin.js").text
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert forbidden not in source
    assert "cookie" not in source.lower()
