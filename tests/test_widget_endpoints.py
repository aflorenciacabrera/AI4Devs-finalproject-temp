import io
import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyhanko.pdf_utils.reader import PdfFileReader
from sqlalchemy import select

from firmadoc.main import app
from firmadoc.models import IntegratingSystem

from .agent_simulator import AgentSimulator
from .test_flow import SIGNER, create
from .test_token_flow import signer_identity, validate_all

WIDGET = "/api/v1/widget/requests"


@pytest.fixture
def anon(client):
    """Cliente sin API key: lo que tiene el navegador."""
    return TestClient(app)


def new_request(client, provider="local", **extra):
    body = create(client, provider=provider, **extra).json()
    _base, _, token = body["signing_url"].partition("#t=")
    return body["id"], token


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# --- contexto -------------------------------------------------------------------------------


def test_contexto_de_una_solicitud_pendiente(client, anon):
    rid, token = new_request(client)
    r = anon.get(f"{WIDGET}/{rid}", headers=bearer(token))
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "id", "status", "provider", "document_name", "signer_name", "allowed_origins",
        "agent_url", "allowed_providers", "token_expires_at", "signed_at", "certificate", "document",
        "signing_status", "signature_deadline", "page_count", "size_bytes",
    }
    assert body["page_count"] == 1 and body["size_bytes"] > 0 and body["signing_status"] == "draft"
    assert body["signature_deadline"] is None
    assert body["status"] == "pending" and body["provider"] == "local"
    assert body["document_name"] == "exp-1_doc-1.pdf"
    assert body["signer_name"] == SIGNER["full_name"]
    assert body["allowed_origins"] == ["http://localhost:4200"]
    assert body["agent_url"] == "http://127.0.0.1:47123"
    assert body["allowed_providers"] == ["local"]
    assert body["document"] is None and body["certificate"] is None


def test_el_contexto_no_expone_datos_del_integrador(client, anon, session):
    rid, token = new_request(client)
    text = anon.get(f"{WIDGET}/{rid}", headers=bearer(token)).text
    system = session.scalars(select(IntegratingSystem)).first()
    assert system.api_key_hash not in text and "firmadoc-demo-key" not in text
    assert "api_key" not in text and "integrating_system" not in text


def test_los_origenes_se_normalizan(client, anon, session):
    system = session.scalars(select(IntegratingSystem)).first()
    system.allowed_origins = " https://a.example.org ,https://b.example.org,, "
    session.commit()
    rid, token = new_request(client)
    body = anon.get(f"{WIDGET}/{rid}", headers=bearer(token)).json()
    assert body["allowed_origins"] == ["https://a.example.org", "https://b.example.org"]


# --- flujo local desde el widget -----------------------------------------------------------


def test_flujo_local_completo_con_el_token_del_widget(client, anon):
    rid, token = new_request(client)
    h = {**bearer(token), "X-Session-Ref": "sesion-1"}
    assert anon.get(f"{WIDGET}/{rid}/download", headers=h).status_code == 409  # antes de firmar

    assert anon.post(f"{WIDGET}/{rid}/prepare", json={}, headers=h).status_code == 200
    r = anon.post(f"{WIDGET}/{rid}/complete", json={"signatures": []}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "signed"
    assert body["signed_at"]
    assert body["document"]["version_number"] == 2
    assert body["document"]["is_active_version"] is True
    assert body["document"]["signed_document_base64"] is None  # el widget no recibe el binario aquí
    assert body["certificate"]["issuer_subject"] and body["certificate"]["serial_number"]

    d = anon.get(f"{WIDGET}/{rid}/download", headers=bearer(token))
    assert d.status_code == 200 and d.headers["content-type"] == "application/pdf"
    assert d.headers["cache-control"] == "no-store"
    assert len(PdfFileReader(io.BytesIO(d.content)).embedded_signatures) == 1

    # el contexto posterior también refleja la firma
    again = anon.get(f"{WIDGET}/{rid}", headers=bearer(token)).json()
    assert again["status"] == "signed" and again["document"]["version_number"] == 2


def test_otra_sesion_no_puede_completar(client, anon):
    rid, token = new_request(client)
    anon.post(f"{WIDGET}/{rid}/prepare", json={}, headers={**bearer(token), "X-Session-Ref": "a"})
    r = anon.post(
        f"{WIDGET}/{rid}/complete", json={"signatures": []},
        headers={**bearer(token), "X-Session-Ref": "b"},
    )
    assert r.status_code == 409


# --- flujo token desde el widget ----------------------------------------------------------


def _token_request(client, pki, **ident_kw):
    ident = signer_identity(pki, **ident_kw)
    rid, token = new_request(client, provider="token")
    return rid, token, ident, AgentSimulator(ident)


def test_flujo_token_completo_con_el_token_del_widget(client, anon, token_env, pki):
    rid, token, _ident, agent = _token_request(client, pki)
    h = {**bearer(token), "X-Session-Ref": "s1"}
    prep = anon.post(f"{WIDGET}/{rid}/prepare", json={"certificate_pem": agent.certificate_pem}, headers=h)
    assert prep.status_code == 200, prep.text
    ch = prep.json()["challenges"][0]
    sig = agent.sign(ch["hash_to_sign"])
    done = anon.post(
        f"{WIDGET}/{rid}/complete",
        json={"signatures": [{"challenge_id": ch["challenge_id"], "signature_base64": sig}]},
        headers=h,
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "signed" and done.json()["provider"] == "token"
    pdf = anon.get(f"{WIDGET}/{rid}/download", headers=bearer(token)).content
    assert validate_all(pdf, pki) == [True]


def test_certificado_revocado_mismo_codigo_que_la_api_de_integracion(client, anon, token_env, pki):
    from .test_token_flow import _revoked  # certificado revocado (con su CRL)

    ident = _revoked(pki)
    pki.write_crls(Path(token_env.crl_dir))
    rid, token = new_request(client, provider="token")
    r = anon.post(
        f"{WIDGET}/{rid}/prepare",
        json={"certificate_pem": ident.pem},
        headers=bearer(token),
    )
    assert (r.status_code, r.json()["code"]) == (422, "certificate_revoked")


def test_cuil_distinto_firma_por_defecto(client, anon, token_env, pki):
    """Sin FIRMADOC_REQUIRE_CUIL_MATCH basta un certificado válido: el PIN del token es el único factor."""
    rid, token = new_request(client, provider="token")
    ajeno = pki.ca.issue("Otra Persona", "20999999995")
    r = anon.post(f"{WIDGET}/{rid}/prepare", json={"certificate_pem": ajeno.pem}, headers=bearer(token))
    assert r.status_code == 200, r.text
    assert "hash_to_sign" in r.json()["challenges"][0]


def test_cuil_distinto_mismo_codigo_con_cotejo(client, anon, token_env, pki):
    token_env.require_cuil_match = True
    rid, token = new_request(client, provider="token")
    ajeno = pki.ca.issue("Otra Persona", "20999999995")
    r = anon.post(f"{WIDGET}/{rid}/prepare", json={"certificate_pem": ajeno.pem}, headers=bearer(token))
    assert (r.status_code, r.json()["code"]) == (403, "cuil_mismatch")


# --- aislamiento de credenciales ------------------------------------------------------------


def test_sin_token(client, anon):
    rid, _ = new_request(client)
    assert anon.get(f"{WIDGET}/{rid}").status_code == 401
    assert anon.get(f"{WIDGET}/{rid}", headers={"Authorization": "Bearer "}).status_code == 401
    assert anon.get(f"{WIDGET}/{rid}", headers={"Authorization": "Basic abc"}).status_code == 401


def test_token_de_otra_solicitud(client, anon):
    rid_a, token_a = new_request(client)
    rid_b, _ = new_request(client)
    r = anon.get(f"{WIDGET}/{rid_b}", headers=bearer(token_a))
    assert r.status_code == 401 and r.json()["code"] == "invalid_token"
    assert anon.post(f"{WIDGET}/{rid_b}/prepare", json={}, headers=bearer(token_a)).status_code == 401
    assert anon.get(f"{WIDGET}/{rid_a}", headers=bearer(token_a)).status_code == 200


def test_token_vencido(client, anon, settings):
    settings.signing_token_ttl_seconds = -1
    rid, token = new_request(client)
    assert anon.get(f"{WIDGET}/{rid}", headers=bearer(token)).status_code == 401


def test_token_alterado(client, anon):
    rid, token = new_request(client)
    bad = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    assert anon.get(f"{WIDGET}/{rid}", headers=bearer(bad)).status_code == 401


def test_el_token_del_widget_no_abre_la_api_de_integracion(client, anon):
    rid, token = new_request(client)
    for path in (
        f"/api/v1/signature-requests/{rid}",
        f"/api/v1/signature-requests/{rid}/prepare",
    ):
        method = anon.post if path.endswith("prepare") else anon.get
        kwargs = {"json": {}} if method == anon.post else {}
        assert method(path, headers={"X-API-Key": token}, **kwargs).status_code == 401
        assert method(path, headers=bearer(token), **kwargs).status_code == 401
    assert anon.get(
        f"/api/v1/documents/{uuid.uuid4()}/versions/1/download", headers={"X-API-Key": token}
    ).status_code == 401


def test_la_api_key_no_abre_los_endpoints_del_widget(client, anon):
    rid, _ = new_request(client)
    for headers in ({"X-API-Key": "firmadoc-demo-key"}, bearer("firmadoc-demo-key")):
        assert anon.get(f"{WIDGET}/{rid}", headers=headers).status_code == 401


def test_el_token_no_aparece_en_las_respuestas_del_widget(client, anon):
    rid, token = new_request(client)
    for r in (
        anon.get(f"{WIDGET}/{rid}", headers=bearer(token)),
        anon.post(f"{WIDGET}/{rid}/prepare", json={}, headers=bearer(token)),
    ):
        assert token not in r.text
        assert token not in json.dumps(dict(r.headers))


def test_documento_de_otro_integrador_inaccesible_con_el_token_de_esta_solicitud(client, anon):
    _rid, token = new_request(client)
    other, _ = new_request(client)
    # el token solo sirve para su propia solicitud, aunque ambas sean del mismo integrador
    assert anon.get(f"{WIDGET}/{other}/download", headers=bearer(token)).status_code == 401
