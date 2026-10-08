"""Firma en lote: creación atómica, preparación, completado con fallos parciales y consulta."""

import base64
import hashlib
import uuid

import pytest
from sqlalchemy import func, select

from firmadoc import integrators, webhooks
from firmadoc.models import (
    AuditEvent,
    BatchStatus,
    Document,
    DocumentVersion,
    RequestStatus,
    SignatureBatch,
    SignatureRequest,
    WebhookDelivery,
)
from firmadoc.services.signature_batch import derive_status

from .agent_simulator import AgentSimulator
from .pdfs import make_pdf
from .test_flow import SIGNER, b64
from .test_token_flow import signer_identity, validate_all

S, F, G, P = RequestStatus.SIGNED, RequestStatus.FAILED, RequestStatus.SIGNING, RequestStatus.PENDING


def docs(n: int) -> list[dict]:
    return [{"document_base64": b64(make_pdf()), "external_document_id": f"lote/doc-{i}"} for i in range(n)]


def create_batch(client, n=3, provider="local", **extra):
    body = {"documents": docs(n), "signer": SIGNER, "provider": provider, **extra}
    return client.post("/api/v1/signature-batches", json=body)


def counts(session) -> tuple[int, int, int]:
    session.expire_all()
    return tuple(
        session.scalar(select(func.count()).select_from(m)) for m in (SignatureBatch, Document, SignatureRequest)
    )


# --- estado derivado ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([P, P], BatchStatus.PENDING),
        ([G, G], BatchStatus.SIGNING),
        ([G, P], BatchStatus.SIGNING),
        ([S, S, S], BatchStatus.COMPLETED),
        ([F, F], BatchStatus.FAILED),
        ([S, F, S], BatchStatus.PARTIAL_FAILURE),
        ([S, G], BatchStatus.PARTIAL_FAILURE),
        ([F, G], BatchStatus.SIGNING),
        ([F, P], BatchStatus.PENDING),
        ([S], BatchStatus.COMPLETED),
    ],
)
def test_estado_derivado(statuses, expected):
    assert derive_status(statuses) == expected


# --- creación ---------------------------------------------------------------------------------------


def test_crear_lote_valido(client, session):
    r = create_batch(client, 3)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending" and body["provider"] == "local"
    assert len(body["requests"]) == 3
    assert len({i["document_id"] for i in body["requests"]}) == 3
    assert all(i["status"] == "pending" and i["error"] is None for i in body["requests"])
    session.expire_all()
    batch = session.get(SignatureBatch, uuid.UUID(body["id"]))
    assert batch is not None
    events = session.scalars(select(AuditEvent.event_type).where(AuditEvent.batch_id == batch.id)).all()
    assert events == ["batch_created"]


def test_un_documento_invalido_no_crea_nada(client, session):
    before = counts(session)
    documents = docs(2) + [{"document_base64": b64(b"no es un pdf")}]
    r = client.post(
        "/api/v1/signature-batches", json={"documents": documents, "signer": SIGNER, "provider": "local"}
    )
    assert r.status_code == 422
    assert counts(session) == before


@pytest.mark.parametrize("n", [0, 51])
def test_cantidad_fuera_de_rango(client, session, n):
    before = counts(session)
    assert create_batch(client, n).status_code == 422
    assert counts(session) == before


def test_limite_configurable(client, settings, session):
    settings.max_batch_size = 2
    assert create_batch(client, 3).status_code == 422
    assert create_batch(client, 2).status_code == 201


def test_documento_existente_en_un_lote(client, session):
    first = create_batch(client, 1).json()["requests"][0]["document_id"]
    r = client.post(
        "/api/v1/signature-batches",
        json={"documents": [{"document_id": first}], "signer": SIGNER, "provider": "local"},
    )
    assert r.status_code == 201
    assert r.json()["requests"][0]["document_id"] == first


def test_documento_ajeno_no_se_acepta(client, session):
    r = client.post(
        "/api/v1/signature-batches",
        json={"documents": [{"document_id": str(uuid.uuid4())}], "signer": SIGNER, "provider": "local"},
    )
    assert r.status_code == 404


def test_requiere_api_key(client):
    r = client.post(
        "/api/v1/signature-batches",
        json={"documents": docs(1), "signer": SIGNER, "provider": "local"},
        headers={"X-API-Key": "invalida"},
    )
    assert r.status_code == 401
    assert client.get(f"/api/v1/signature-batches/{uuid.uuid4()}", headers={"X-API-Key": ""}).status_code == 401


def test_aislamiento_entre_integradores(client, session):
    batch_id = create_batch(client, 1).json()["id"]
    _system, other_key, _secret = integrators.create(session, "Otro integrador", "")
    other = {"X-API-Key": other_key}
    assert client.get(f"/api/v1/signature-batches/{batch_id}", headers=other).status_code == 404
    assert client.post(f"/api/v1/signature-batches/{batch_id}/prepare", json={}, headers=other).status_code == 404
    assert client.post(f"/api/v1/signature-batches/{batch_id}/complete", json={}, headers=other).status_code == 404


# --- proveedor local de punta a punta -------------------------------------------------------------


def test_lote_local_de_punta_a_punta(client, session):
    created = create_batch(client, 3).json()
    batch_id = created["id"]
    p = client.post(f"/api/v1/signature-batches/{batch_id}/prepare", json={})
    assert p.status_code == 200, p.text
    assert len(p.json()["challenges"]) == 3
    assert {c["signature_request_id"] for c in p.json()["challenges"]} == {
        i["signature_request_id"] for i in created["requests"]
    }
    assert client.get(f"/api/v1/signature-batches/{batch_id}").json()["status"] == "signing"

    c = client.post(f"/api/v1/signature-batches/{batch_id}/complete", json={"signatures": []})
    assert c.status_code == 200, c.text
    done = c.json()
    assert done["status"] == "completed" and done["completed_at"] is not None
    assert all(i["status"] == "signed" and i["version_number"] == 2 for i in done["requests"])
    assert "signed_document_base64" not in c.text

    for item in done["requests"]:  # cada documento tiene su versión inmutable y descargable
        assert client.get(item["download_url"].replace("http://test", "")).status_code == 200
    session.expire_all()
    versions = session.scalars(select(DocumentVersion).where(DocumentVersion.version_number == 2)).all()
    assert len(versions) >= 3
    events = session.scalars(
        select(AuditEvent.event_type).where(AuditEvent.batch_id == uuid.UUID(batch_id)).order_by(AuditEvent.created_at)
    ).all()
    assert set(events) == {"batch_created", "batch_prepared", "batch_completed"}
    for item in done["requests"]:
        kinds = set(
            session.scalars(
                select(AuditEvent.event_type).where(
                    AuditEvent.signature_request_id == uuid.UUID(item["signature_request_id"])
                )
            )
        )
        assert {"created", "prepared", "signed"} <= kinds


def test_lote_ya_completado_o_sin_preparar_da_409(client):
    batch_id = create_batch(client, 2).json()["id"]
    assert client.post(f"/api/v1/signature-batches/{batch_id}/complete", json={}).status_code == 409  # sin preparar
    client.post(f"/api/v1/signature-batches/{batch_id}/prepare", json={})
    assert client.post(f"/api/v1/signature-batches/{batch_id}/complete", json={}).status_code == 200
    again = client.post(f"/api/v1/signature-batches/{batch_id}/complete", json={})
    assert again.status_code == 409
    assert client.post(f"/api/v1/signature-batches/{batch_id}/prepare", json={}).status_code == 409


def test_webhook_por_documento(client, session, monkeypatch):
    monkeypatch.setattr(webhooks, "RESOLVER", lambda host, port: ["93.184.216.34"])
    batch_id = create_batch(client, 3, callback_url="https://hooks.example.org/in").json()["id"]
    client.post(f"/api/v1/signature-batches/{batch_id}/prepare", json={})
    client.post(f"/api/v1/signature-batches/{batch_id}/complete", json={})
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(WebhookDelivery)) == 3


def test_callback_invalido_en_el_lote_no_crea_nada(client, session):
    before = counts(session)
    assert create_batch(client, 2, callback_url="http://hooks.example.org/in").status_code == 422
    assert counts(session) == before


# --- proveedor token (un hash por documento, una sola sesión) -------------------------------------


def token_batch(client, pki, n=3):
    agent = AgentSimulator(signer_identity(pki))
    batch_id = create_batch(client, n, provider="token").json()["id"]
    prepared = client.post(
        f"/api/v1/signature-batches/{batch_id}/prepare", json={"certificate_pem": agent.certificate_pem}
    )
    assert prepared.status_code == 200, prepared.text
    return agent, batch_id, prepared.json()["challenges"]


def test_lote_token_firma_todo_con_un_solo_certificado(client, session, token_env, pki):
    agent, batch_id, challenges = token_batch(client, pki)
    assert len({c["hash_to_sign"] for c in challenges}) == 3  # un hash distinto por documento
    signatures = [
        {"challenge_id": c["challenge_id"], "signature_base64": agent.sign(c["hash_to_sign"])} for c in challenges
    ]
    r = client.post(f"/api/v1/signature-batches/{batch_id}/complete", json={"signatures": signatures})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"
    for item in r.json()["requests"]:
        pdf = client.get(item["download_url"].replace("http://test", "")).content
        assert validate_all(pdf, pki) == [True]


def test_firma_invalida_es_fallo_parcial(client, session, token_env, pki):
    agent, batch_id, challenges = token_batch(client, pki)
    signatures = [
        {"challenge_id": c["challenge_id"], "signature_base64": agent.sign(c["hash_to_sign"])} for c in challenges
    ]
    signatures[1]["signature_base64"] = agent.sign(base64.b64encode(hashlib.sha256(b"otro").digest()).decode())
    r = client.post(f"/api/v1/signature-batches/{batch_id}/complete", json={"signatures": signatures})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "partial_failure"
    by_status = sorted(i["status"] for i in body["requests"])
    assert by_status == ["failed", "signed", "signed"]
    failed = next(i for i in body["requests"] if i["status"] == "failed")
    assert failed["error"]["http_status"] == 422 and failed["version_number"] is None
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(DocumentVersion).where(DocumentVersion.version_number == 2)) >= 2


def test_firma_faltante_deja_la_solicitud_sin_cambios(client, session, token_env, pki):
    agent, batch_id, challenges = token_batch(client, pki)
    signatures = [
        {"challenge_id": c["challenge_id"], "signature_base64": agent.sign(c["hash_to_sign"])}
        for c in challenges[:2]
    ]
    r = client.post(f"/api/v1/signature-batches/{batch_id}/complete", json={"signatures": signatures})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "partial_failure"
    missing = next(i for i in body["requests"] if i["status"] == "signing")
    assert missing["error"] is not None

    # se puede completar después con la firma que faltaba
    last = challenges[2]
    again = client.post(
        f"/api/v1/signature-batches/{batch_id}/complete",
        json={"signatures": [{"challenge_id": last["challenge_id"], "signature_base64": agent.sign(last["hash_to_sign"])}]},
    )
    assert again.status_code == 200 and again.json()["status"] == "completed"


def test_desafio_de_otro_lote_se_rechaza(client, token_env, pki):
    agent, batch_a, challenges_a = token_batch(client, pki, 1)
    _agent, batch_b, _challenges_b = token_batch(client, pki, 1)
    c = challenges_a[0]
    r = client.post(
        f"/api/v1/signature-batches/{batch_b}/complete",
        json={"signatures": [{"challenge_id": c["challenge_id"], "signature_base64": agent.sign(c["hash_to_sign"])}]},
    )
    assert r.status_code == 409
    assert client.get(f"/api/v1/signature-batches/{batch_a}").json()["status"] == "signing"


def test_desafio_repetido_en_el_mismo_lote_se_rechaza(client, token_env, pki):
    agent, batch_id, challenges = token_batch(client, pki, 2)
    c = challenges[0]
    sig = {"challenge_id": c["challenge_id"], "signature_base64": agent.sign(c["hash_to_sign"])}
    r = client.post(f"/api/v1/signature-batches/{batch_id}/complete", json={"signatures": [sig, sig]})
    assert r.status_code == 422


def test_certificado_rechazado_no_prepara_ninguno(client, session, token_env, pki):
    batch_id = create_batch(client, 3, provider="token").json()["id"]
    stranger = AgentSimulator(pki.ca.issue("Otra Persona", "27999999990"))  # CUIL que no es del firmante
    r = client.post(
        f"/api/v1/signature-batches/{batch_id}/prepare", json={"certificate_pem": stranger.certificate_pem}
    )
    assert r.status_code == 403
    session.expire_all()
    statuses = {s for (s,) in session.execute(select(SignatureRequest.status).where(SignatureRequest.batch_id == uuid.UUID(batch_id)))}
    assert statuses == {RequestStatus.PENDING}
