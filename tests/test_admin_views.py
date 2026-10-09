"""Vistas de auditoría del panel: origen, versión y vencimiento, línea de tiempo, detalle técnico y descargas."""

import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pyhanko.pdf_utils.reader import PdfFileReader
from sqlalchemy import select

from firmadoc.models import (
    DeliveryStatus,
    SigningStatus,
    WebhookDelivery,
)

from .agent_simulator import AgentSimulator
from .pdfs import make_pdf
from .test_flow import SIGNER, create, sign_fully
from .test_signature_batches import create_batch
from .test_token_flow import prepare, run_token_flow, signer_identity

TOKEN = "t0ken-de-administracion-" + "x" * 20


@pytest.fixture
def admin(client, settings):
    settings.admin_token = TOKEN
    return {"Authorization": f"Bearer {TOKEN}"}


def listing(client, admin, **params):
    r = client.get("/api/v1/admin/signature-requests", headers=admin, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def batch_sign(client, n=3):
    body = create_batch(client, n).json()
    client.post(f"/api/v1/signature-batches/{body['id']}/prepare", json={})
    client.post(f"/api/v1/signature-batches/{body['id']}/complete", json={})
    return body["id"]


# --- listado: origen, vencimiento, filtros ----------------------------------------------------------


def test_origen_individual_y_de_lote(client, admin):
    sign_fully(client)
    batch_id = batch_sign(client, 2)
    items = listing(client, admin)["items"]
    kinds = [i["origin"]["kind"] for i in items]
    assert kinds.count("batch") == 2 and kinds.count("individual") >= 1
    labeled = [i["origin"] for i in items if i["origin"]["kind"] == "batch"]
    assert {o["batch_id"] for o in labeled} == {batch_id}
    assert labeled[0]["label"] == "#" + batch_id[:8]


def test_las_filas_de_un_lote_quedan_juntas(client, admin):
    batch_id = batch_sign(client, 3)
    sign_fully(client)  # individual posterior
    batch_sign(client, 2)  # otro lote posterior
    sign_fully(client)
    origins = [i["origin"].get("batch_id") for i in listing(client, admin)["items"]]
    positions = [k for k, b in enumerate(origins) if b == batch_id]
    assert len(positions) == 3 and positions == list(range(positions[0], positions[0] + 3))


def test_filtro_por_origen(client, admin):
    sign_fully(client)
    batch_sign(client, 2)
    assert {i["origin"]["kind"] for i in listing(client, admin, origin="batch")["items"]} == {"batch"}
    assert {i["origin"]["kind"] for i in listing(client, admin, origin="individual")["items"]} == {"individual"}
    assert client.get("/api/v1/admin/signature-requests", headers=admin, params={"origin": "otro"}).status_code == 422


def test_el_vencimiento_se_informa(client, admin, session):
    created = create(client).json()
    deadline = datetime.now(UTC) + timedelta(days=5)
    r = client.patch(
        f"/api/v1/documents/{created['document_id']}",
        json={"signing_status": "pending_signature", "signature_deadline": deadline.isoformat()},
    )
    assert r.status_code == 200, r.text
    item = next(i for i in listing(client, admin)["items"] if i["id"] == created["id"])
    assert item["document"]["signature_deadline"] is not None
    assert item["document"]["signing_status"] == SigningStatus.PENDING_SIGNATURE.value


def test_busqueda_por_documento_y_por_firmante(client, admin):
    create(client, external_document_id="Providencia_0098")
    create(client, external_document_id="Oficio_0231")
    by_doc = listing(client, admin, q="providencia")["items"]
    assert [i["document"]["external_document_id"] for i in by_doc] == ["Providencia_0098"]
    assert len(listing(client, admin, q=SIGNER["full_name"][:4])["items"]) == 2  # por firmante
    assert len(listing(client, admin, q=SIGNER["identifier"])["items"]) == 2
    assert listing(client, admin, q="no-existe")["total"] == 0


@pytest.mark.parametrize("hostile", ["%", "_", "\\", "' OR 1=1 --", "%_%"])
def test_la_busqueda_escapa_comodines(client, admin, hostile):
    create(client, external_document_id="DocumentoA")
    assert listing(client, admin, q=hostile)["total"] == 0


def test_el_filtro_signer_sigue_funcionando(client, admin):
    create(client)
    assert listing(client, admin, signer=SIGNER["identifier"])["total"] == 1


# --- custodia: línea de tiempo y datos técnicos -----------------------------------------------------


def custody(client, admin, document_id):
    r = client.get(f"/api/v1/admin/documents/{document_id}/custody", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()


def test_la_historia_de_una_firma_con_token(client, admin, token_env, pki):
    agent = AgentSimulator(signer_identity(pki))
    _, r = run_token_flow(client, agent)
    assert r.status_code == 200, r.text
    body = custody(client, admin, r.json()["document_id"])
    timeline = body["timeline"]
    titles = [t["title"] for t in timeline]
    assert titles[0] == "Solicitud creada por el sistema integrador"
    assert "Desafío preparado: hash SHA-256 a firmar" in titles
    assert "Firma recibida del agente local" in titles
    assert any(t.startswith("Nueva versión registrada: v2") for t in titles)
    assert titles.index("Desafío preparado: hash SHA-256 a firmar") < titles.index("Firma recibida del agente local")
    assert timeline[0]["actor"] == body["document"]["integrating_system_name"]
    actors = {t["actor"] for t in timeline}
    assert {"Firmadoc Agent", "Motor Firmadoc"} <= actors
    assert [t["at"] for t in timeline] == sorted(t["at"] for t in timeline)
    # los datos crudos se conservan
    assert body["signature_requests"][0]["events"] and body["versions"]


def test_el_certificado_rechazado_aparece_en_la_historia(client, admin, token_env, pki):
    rid = create(client, provider="token").json()["id"]
    ajeno = pki.ca.issue("Otra Persona", "20999999995")
    assert prepare(client, rid, ajeno.pem).status_code == 403
    document_id = client.get(f"/api/v1/signature-requests/{rid}").json()["document_id"]
    timeline = custody(client, admin, document_id)["timeline"]
    rejected = next(t for t in timeline if t["title"] == "Certificado rechazado")
    assert rejected["kind"] == "error" and rejected["detail"]
    assert not any(t["title"] == "Desafío preparado: hash SHA-256 a firmar" for t in timeline)


def test_la_firma_fallida_y_el_webhook_fallido_aparecen(client, admin, session, monkeypatch):
    from firmadoc import webhooks

    monkeypatch.setattr(webhooks, "RESOLVER", lambda host, port: ["93.184.216.34"])
    document_id = sign_fully(client, callback_url="https://hooks.example.org/in")["document_id"]
    session.expire_all()
    delivery = session.scalar(select(WebhookDelivery))
    delivery.status, delivery.attempts, delivery.response_status = DeliveryStatus.FAILED, 6, 500
    session.commit()
    timeline = custody(client, admin, document_id)["timeline"]
    hook = next(t for t in timeline if t["title"].startswith("Webhook"))
    assert hook["title"] == "Webhook fallido" and hook["kind"] == "error"
    assert "Intento 6" in hook["detail"] and "500" in hook["detail"]


def test_un_evento_desconocido_no_se_pierde(client, admin, session):
    from firmadoc.models import AuditEvent, SignatureRequest

    created = create(client).json()
    request = session.get(SignatureRequest, uuid.UUID(created["id"]))
    session.add(AuditEvent(signature_request_id=request.id, event_type="evento_futuro", payload={}))
    session.commit()
    titles = [t["title"] for t in custody(client, admin, created["document_id"])["timeline"]]
    assert "evento_futuro" in titles


def test_los_eventos_de_lote_no_ensucian_la_historia(client, admin):
    batch_sign(client, 2)
    first = listing(client, admin)["items"][0]["document"]["id"]
    titles = [t["title"] for t in custody(client, admin, first)["timeline"]]
    assert not any(t.startswith("batch_") for t in titles)


def test_detalle_tecnico_de_una_firma_completa(client, admin, token_env, pki):
    agent = AgentSimulator(signer_identity(pki))
    _rid, r = run_token_flow(client, agent)
    body = custody(client, admin, r.json()["document_id"])
    tech = body["technical"]
    assert tech["transaction_id"] == _rid
    assert tech["provider"] == "token" and tech["signature_level"] == "B-B"
    assert tech["certificate"]["subject"] and tech["certificate"]["issuer_subject"] and tech["certificate"]["serial_number"]
    assert tech["signer"]["identifier"] == SIGNER["identifier"]
    versions = {v["version_number"]: v for v in body["versions"]}
    assert tech["original_hash"] == versions[1]["document_hash"]
    assert tech["signed_hash"] == versions[2]["document_hash"] and tech["original_hash"] != tech["signed_hash"]
    assert "ip" not in str(tech).lower().replace("provider", "")  # el sistema no registra la IP de origen


def test_sin_firma_no_hay_detalle_tecnico(client, admin):
    created = create(client).json()
    assert custody(client, admin, created["document_id"])["technical"] is None


def test_la_custodia_sigue_sin_datos_sensibles(client, admin):
    document_id = sign_fully(client)["document_id"]
    raw = client.get(f"/api/v1/admin/documents/{document_id}/custody", headers=admin).text
    assert "hash_to_sign" not in raw and "signed_document_base64" not in raw and '"body"' not in raw


# --- descarga de versiones -------------------------------------------------------------------------


def test_descargar_la_v1_original_y_la_v2_firmada(client, admin):
    pdf = make_pdf(b"BT original ET")
    created = create(client, pdf=pdf).json()
    client.post(f"/api/v1/signature-requests/{created['id']}/prepare", json={})
    assert client.post(f"/api/v1/signature-requests/{created['id']}/complete", json={}).status_code == 200
    base = f"/api/v1/admin/documents/{created['document_id']}/versions"
    v1 = client.get(f"{base}/1/download", headers=admin)
    v2 = client.get(f"{base}/2/download", headers=admin)
    assert v1.status_code == v2.status_code == 200
    assert v1.headers["content-type"] == "application/pdf" and v1.headers["cache-control"] == "no-store"
    assert v1.content == pdf
    assert len(PdfFileReader(io.BytesIO(v1.content)).embedded_signatures) == 0
    assert len(PdfFileReader(io.BytesIO(v2.content)).embedded_signatures) == 1
    assert "-v1.pdf" in v1.headers["content-disposition"] and "-v2.pdf" in v2.headers["content-disposition"]


def test_descarga_inexistente_o_sin_credenciales(client, admin):
    created = create(client).json()
    base = f"/api/v1/admin/documents/{created['document_id']}/versions"
    assert client.get(f"{base}/9/download", headers=admin).status_code == 404
    assert client.get(f"/api/v1/admin/documents/{uuid.uuid4()}/versions/1/download", headers=admin).status_code == 404
    assert client.get(f"{base}/1/download").status_code == 401
    assert client.get(f"{base}/1/download", headers={"Authorization": "Bearer otro"}).status_code == 401


def test_el_nombre_de_archivo_descargado_se_sanea(client, admin):
    created = create(client, external_document_id='exp/"1"\r\nX: y').json()
    r = client.get(f"/api/v1/admin/documents/{created['document_id']}/versions/1/download", headers=admin)
    assert r.status_code == 200
    disposition = r.headers["content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition and '"1"' not in disposition
