"""Proveedor `firmar` (firma remota) contra el servicio simulado: flujo, callback y validación del PDF."""

import base64
import json
import socket
import threading
import time
import uuid

import httpx
import pytest
import uvicorn
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from firmadoc import mock_firmar, webhooks
from firmadoc.api.deps import settings_dep
from firmadoc.config import Settings
from firmadoc.db import make_engine
from firmadoc.main import app
from firmadoc.models import (
    AuditEvent,
    Certificate,
    Provider,
    RequestStatus,
    SignatureRequest,
    SigningChallenge,
    WebhookDelivery,
)
from firmadoc.providers import firmar
from firmadoc.seed import DEMO_API_KEY

from .conftest import alembic_config
from .pdfs import make_pdf
from .test_flow import SIGNER, b64

CLIENT_SECRET = "secreto-del-cliente-firmar"
CALLBACK_SECRET = "secreto-del-callback-" + "x" * 24
CUIL = SIGNER["identifier"]


@pytest.fixture
def firmar_env(settings, client, monkeypatch):
    settings.firmar_base_url = "http://test/mock/firmar"
    settings.firmar_client_secret = CLIENT_SECRET
    settings.firmar_callback_secret = CALLBACK_SECRET
    settings.firmar_mock_enabled = True
    settings.trust_dir = str(settings.storage_dir) + "-sin-anclas"  # solo cuenta la AC del simulado
    mock_firmar.reset()

    def forward(request: httpx.Request) -> httpx.Response:
        r = TestClient(app).request(request.method, str(request.url), content=request.content, headers=dict(request.headers))
        return httpx.Response(r.status_code, content=r.content, headers={"content-type": r.headers.get("content-type", "")})

    monkeypatch.setattr(firmar, "TRANSPORT", httpx.MockTransport(forward))
    monkeypatch.setattr(webhooks, "RESOLVER", lambda host, port: ["93.184.216.34"])
    yield settings
    mock_firmar.reset()


def mock_token(client, secret=CLIENT_SECRET) -> str:
    r = client.post(
        "/mock/firmar/oauth/token",
        content=f"grant_type=client_credentials&client_id=firmadoc&client_secret={secret}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def new_request(client, pdf: bytes | None = None, **extra) -> str:
    body = {
        "document_base64": b64(pdf or make_pdf()),
        "external_document_id": "exp-remoto/1",
        "signer": SIGNER,
        "provider": "firmar",
        **extra,
    }
    r = client.post("/api/v1/signature-requests", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def prepared(client, **extra) -> tuple[str, str]:
    rid = new_request(client, **extra)
    r = client.post(f"/api/v1/signature-requests/{rid}/prepare", json={})
    assert r.status_code == 200, r.text
    return rid, r.json()["remote"]["operation_id"]


def approve(client, operation_id, otp="123456", pin="1234"):
    token = mock_token(client)
    return client.post(
        f"/mock/firmar/v1/operations/{operation_id}/approve",
        json={"otp": otp, "pin": pin},
        headers={"Authorization": f"Bearer {token}"},
    )


def post_callback(client, payload: dict | bytes, secret=CALLBACK_SECRET, header: str | None = "auto"):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if header == "auto":
        headers[firmar.SIGNATURE_HEADER] = firmar.callback_signature(secret, body)
    elif header:
        headers[firmar.SIGNATURE_HEADER] = header
    return client.post("/api/v1/providers/firmar/callback", content=body, headers=headers)


def status_of(client, rid) -> str:
    return client.get(f"/api/v1/signature-requests/{rid}").json()["status"]


# --- habilitación y configuración -------------------------------------------------------------------


def test_sin_configurar_no_esta_habilitado(client):
    r = client.post(
        "/api/v1/signature-requests",
        json={"document_base64": b64(make_pdf()), "signer": SIGNER, "provider": "firmar"},
    )
    assert r.status_code == 422 and "habilitado" in r.json()["detail"]


def test_configuracion_invalida():
    with pytest.raises(ValueError):
        Settings(firmar_callback_secret="corto")
    with pytest.raises(ValueError):
        Settings(firmar_base_url="ftp://servicio")
    assert Settings(firmar_base_url="").firmar_base_url is None


def test_callback_sin_proveedor_configurado_no_existe(client):
    assert post_callback(client, {"operation_id": "x", "status": "signed"}).status_code == 404


def test_simulado_deshabilitado(client, firmar_env):
    firmar_env.firmar_mock_enabled = False
    assert client.post("/mock/firmar/oauth/token", content="grant_type=client_credentials").status_code == 404
    assert client.post("/mock/firmar/v1/operations", json={}).status_code == 404


# --- servicio simulado --------------------------------------------------------------------------------


def test_oauth_simulado(client, firmar_env):
    assert mock_token(client)
    bad = client.post(
        "/mock/firmar/oauth/token",
        content="grant_type=client_credentials&client_id=firmadoc&client_secret=incorrecto",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert bad.status_code == 401 and bad.json()["error"] == "invalid_client"
    other = client.post("/mock/firmar/oauth/token", content="grant_type=password&client_id=firmadoc")
    assert other.status_code == 401
    no_token = client.post("/mock/firmar/v1/operations", json={"document_base64": b64(make_pdf()), "signer_cuil": CUIL, "callback_url": "http://x"})
    assert no_token.status_code == 401
    assert client.get("/mock/firmar/v1/operations/x", headers={"Authorization": "Bearer inventado"}).status_code == 401


def test_simulado_admite_un_documento_por_operacion(client, firmar_env):
    token = mock_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    two = {"documents": [b64(make_pdf()), b64(make_pdf())], "signer_cuil": CUIL, "callback_url": "http://x"}
    assert client.post("/mock/firmar/v1/operations", json=two, headers=headers).status_code == 422
    bad = {"document_base64": b64(b"no es pdf"), "signer_cuil": CUIL, "callback_url": "http://x"}
    assert client.post("/mock/firmar/v1/operations", json=bad, headers=headers).status_code == 422


def test_otp_incorrecto_y_bloqueo(client, firmar_env, session):
    rid, op = prepared(client)
    assert approve(client, op, otp="000000").status_code == 403
    assert approve(client, op, pin="9999").status_code == 403
    locked = approve(client, op, otp="x")
    assert locked.status_code == 403 and locked.json()["error"] == "locked"
    assert approve(client, op).status_code == 409  # bloqueada: ni con los datos correctos
    assert status_of(client, rid) == "signing"  # el callback nunca se llamó


# --- flujo completo -----------------------------------------------------------------------------------


def test_prepare_remoto(client, firmar_env, session):
    rid = new_request(client)
    r = client.post(f"/api/v1/signature-requests/{rid}/prepare", json={})
    body = r.json()
    assert r.status_code == 200 and body["challenges"] == [] and body["expires_at"]
    assert body["remote"]["operation_id"] and "authorization_url" in body["remote"]
    assert status_of(client, rid) == "signing"
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(SigningChallenge)) == 0
    assert session.get(SignatureRequest, uuid.UUID(rid)).remote_operation_id == body["remote"]["operation_id"]
    again = client.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})
    assert again.status_code == 409 and again.json()["code"] == "remote_signature_pending"


def test_flujo_remoto_de_punta_a_punta(client, firmar_env, session):
    rid, op = prepared(client, callback_url="https://hooks.example.org/in")
    a = approve(client, op)
    assert a.status_code == 200 and a.json()["callback_status"] == 200, a.text

    result = client.get(f"/api/v1/signature-requests/{rid}").json()
    assert result["status"] == "signed" and result["provider"] == "firmar"
    assert result["document"]["version_number"] == 2 and result["document"]["is_active_version"] is True
    assert result["certificate"]["subject"]
    session.expire_all()
    cert = session.scalar(select(Certificate).where(Certificate.provider == Provider.FIRMAR))
    assert cert is not None and cert.cuil == CUIL and cert.signer_id is not None
    kinds = [e.event_type for e in session.scalars(select(AuditEvent).where(AuditEvent.signature_request_id == uuid.UUID(rid)).order_by(AuditEvent.created_at))]
    assert kinds == ["created", "prepared", "signed"]
    assert session.scalar(select(func.count()).select_from(WebhookDelivery)) == 1  # webhook como cualquier firma

    verify = client.post(f"/api/v1/documents/{result['document_id']}/verify").json()
    assert verify["valid"] is True and len(verify["signatures"]) == 1
    sigs = client.get(f"/api/v1/documents/{result['document_id']}/signatures").json()
    assert sigs[0]["provider"] == "firmar"
    original = client.get(f"/api/v1/documents/{result['document_id']}/versions/1/download")
    signed = client.get(f"/api/v1/documents/{result['document_id']}/versions/2/download")
    assert signed.content.startswith(original.content)  # actualización incremental: la v1 queda intacta


# --- callback -------------------------------------------------------------------------------------------


def test_firma_del_callback(client, firmar_env):
    rid, op = prepared(client)
    payload = {"operation_id": op, "status": "rejected"}
    assert post_callback(client, payload, header=None).status_code == 401
    assert post_callback(client, payload, header="sha256=" + "0" * 64).status_code == 401
    assert post_callback(client, payload, secret="otro-secreto-" + "y" * 30).status_code == 401
    assert status_of(client, rid) == "signing"


def test_operacion_desconocida_y_cuerpo_invalido(client, firmar_env):
    assert post_callback(client, {"operation_id": "no-existe", "status": "rejected"}).status_code == 404
    assert post_callback(client, b"esto no es json").status_code == 422
    assert post_callback(client, {"status": "signed"}).status_code == 422
    assert post_callback(client, {"operation_id": "x", "status": "otro"}).status_code == 422


def test_repeticion_es_idempotente(client, firmar_env, session):
    rid, op = prepared(client)
    assert approve(client, op).status_code == 200
    again = post_callback(client, {"operation_id": op, "status": "signed", "signed_document_base64": b64(b"%PDF-1.4 basura")})
    assert again.status_code == 200 and again.json()["status"] == "already_processed"
    versions = client.get(f"/api/v1/signature-requests/{rid}").json()["document"]["version_number"]
    assert versions == 2


@pytest.mark.parametrize("status", ["rejected", "expired"])
def test_rechazo_o_vencimiento(client, firmar_env, session, status):
    rid, op = prepared(client, callback_url="https://hooks.example.org/in")
    assert post_callback(client, {"operation_id": op, "status": status}).status_code == 200
    assert status_of(client, rid) == "failed"
    session.expire_all()
    events = session.scalars(select(AuditEvent).where(AuditEvent.signature_request_id == uuid.UUID(rid))).all()
    failed = next(e for e in events if e.event_type == "failed")
    assert failed.payload["code"] == f"remote_{status}"
    delivery = session.scalar(select(WebhookDelivery))
    assert delivery.event_type == webhooks.EVENT_FAILED
    assert post_callback(client, {"operation_id": op, "status": "rejected"}).json()["status"] == "already_processed"


def test_rechazo_desde_el_simulado(client, firmar_env):
    rid, op = prepared(client)
    token = mock_token(client)
    r = client.post(f"/mock/firmar/v1/operations/{op}/reject", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and status_of(client, rid) == "failed"


# --- validación del PDF devuelto ------------------------------------------------------------------------


def original_of(client, rid) -> bytes:
    document_id = client.get(f"/api/v1/signature-requests/{rid}").json()["document_id"]
    return client.get(f"/api/v1/documents/{document_id}/versions/1/download").content


def signed_callback(client, op, pdf: bytes):
    return post_callback(client, {"operation_id": op, "status": "signed", "signed_document_base64": b64(pdf)})


def expect_rejected(client, session, rid, response, code=None):
    assert response.status_code == 422, response.text
    if code:
        assert response.json()["code"] == code
    assert status_of(client, rid) == "failed"
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(SignatureRequest).where(SignatureRequest.status == RequestStatus.SIGNED)) == 1  # solo el del seed


def test_contenido_alterado(client, firmar_env, session):
    rid, op = prepared(client)
    other_signed = mock_firmar._sign_pdf(firmar_env, make_pdf(), CUIL)  # firma sobre otro PDF distinto
    expect_rejected(client, session, rid, signed_callback(client, op, other_signed), "remote_invalid_document")


def test_sin_firma_nueva(client, firmar_env, session):
    rid, op = prepared(client)
    expect_rejected(client, session, rid, signed_callback(client, op, original_of(client, rid)), "remote_invalid_document")


def test_dos_firmas_nuevas(client, firmar_env, session):
    rid, op = prepared(client)
    once = mock_firmar._sign_pdf(firmar_env, original_of(client, rid), CUIL)
    twice = mock_firmar._sign_pdf(firmar_env, once, CUIL)
    expect_rejected(client, session, rid, signed_callback(client, op, twice), "remote_invalid_document")


def test_cuil_distinto(client, firmar_env, session):
    rid, op = prepared(client)
    forged = mock_firmar._sign_pdf(firmar_env, original_of(client, rid), "27999999990")
    expect_rejected(client, session, rid, signed_callback(client, op, forged), "cuil_mismatch")


def test_cadena_desconocida(client, firmar_env, session, pki):
    from asn1crypto import keys
    from asn1crypto import x509 as ax509
    from cryptography.hazmat.primitives import serialization
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    from pyhanko.sign.fields import SigSeedSubFilter
    from pyhanko.sign.signers.pdf_signer import PdfSignatureMetadata
    from pyhanko_certvalidator.registry import SimpleCertificateStore

    rid, op = prepared(client)
    identity = pki.ca.issue("Persona Ajena", CUIL)  # certificado válido pero de una AC que no es ancla
    registry = SimpleCertificateStore()
    registry.register(ax509.Certificate.load(pki.ca.der))
    signer = signers.SimpleSigner(
        signing_cert=ax509.Certificate.load(identity.der),
        signing_key=keys.PrivateKeyInfo.load(
            identity.key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        ),
        cert_registry=registry,
    )
    import io

    out = signers.sign_pdf(
        IncrementalPdfFileWriter(io.BytesIO(original_of(client, rid))),
        PdfSignatureMetadata(field_name="Firmadoc-1", md_algorithm="sha256", subfilter=SigSeedSubFilter.PADES),
        signer=signer,
    )
    expect_rejected(client, session, rid, signed_callback(client, op, out.getvalue()), "certificate_untrusted")


def test_cuerpo_de_firma_invalido(client, firmar_env, session):
    rid, op = prepared(client)
    assert post_callback(client, {"operation_id": op, "status": "signed"}).status_code == 422
    assert post_callback(client, {"operation_id": op, "status": "signed", "signed_document_base64": "###"}).status_code == 422
    assert status_of(client, rid) == "signing"  # el cuerpo mal formado no consume la solicitud
    not_pdf = signed_callback(client, op, b"esto no es un pdf")
    expect_rejected(client, session, rid, not_pdf, "remote_invalid_document")


def test_documento_devuelto_demasiado_grande(client, firmar_env, session):
    rid, op = prepared(client)
    firmar_env.max_document_bytes = 100
    expect_rejected(client, session, rid, signed_callback(client, op, mock_firmar._sign_pdf(firmar_env, original_of(client, rid), CUIL)), "remote_invalid_document")


# --- servicio caído -------------------------------------------------------------------------------------


def test_credenciales_incorrectas_dan_503_sin_filtrar(client, firmar_env, session, monkeypatch):
    good = firmar.TRANSPORT

    def wrong_secret(request: httpx.Request) -> httpx.Response:  # el cliente envía otro secreto que el esperado
        content = request.content.replace(CLIENT_SECRET.encode(), b"secreto-equivocado")
        return good.handle_request(httpx.Request(request.method, request.url, headers=request.headers, content=content))

    monkeypatch.setattr(firmar, "TRANSPORT", httpx.MockTransport(wrong_secret))
    rid = new_request(client)
    r = client.post(f"/api/v1/signature-requests/{rid}/prepare", json={})
    assert r.status_code == 503 and r.json()["code"] == "remote_unavailable"
    assert "invalid_client" not in r.text and "secreto" not in r.text
    assert status_of(client, rid) == "pending"


def test_servicio_caido(client, firmar_env, monkeypatch):
    def down(request):
        raise httpx.ConnectError("sin conexion")

    monkeypatch.setattr(firmar, "TRANSPORT", httpx.MockTransport(down))
    rid = new_request(client)
    r = client.post(f"/api/v1/signature-requests/{rid}/prepare", json={})
    assert r.status_code == 503 and r.json()["code"] == "remote_unavailable"
    assert status_of(client, rid) == "pending"


def test_servicio_responde_basura(client, firmar_env, monkeypatch):
    monkeypatch.setattr(firmar, "TRANSPORT", httpx.MockTransport(lambda r: httpx.Response(200, content=b"<html>")))
    rid = new_request(client)
    assert client.post(f"/api/v1/signature-requests/{rid}/prepare", json={}).status_code == 503


# --- migración ------------------------------------------------------------------------------------------


def test_migracion_0004_reversible_y_unica(db_url):
    cfg = alembic_config(db_url)
    command.upgrade(cfg, "0003")
    engine = make_engine(db_url)
    assert "remote_operation_id" not in {c["name"] for c in inspect(engine).get_columns("signature_request")}
    command.upgrade(cfg, "0004")
    assert "remote_operation_id" in {c["name"] for c in inspect(engine).get_columns("signature_request")}
    command.downgrade(cfg, "0003")
    assert "remote_operation_id" not in {c["name"] for c in inspect(engine).get_columns("signature_request")}
    command.upgrade(cfg, "head")
    engine.dispose()


def test_operacion_remota_unica(client, firmar_env, session):
    _rid, op = prepared(client)
    other = new_request(client)
    session.expire_all()
    session.get(SignatureRequest, uuid.UUID(other)).remote_operation_id = op
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# --- camino HTTP real -----------------------------------------------------------------------------------


@pytest.fixture
def live_server(settings, session):
    from firmadoc.seed import seed_demo

    seed_demo(session)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    settings.public_base_url = base
    settings.firmar_base_url = f"{base}/mock/firmar"
    settings.firmar_client_secret = CLIENT_SECRET
    settings.firmar_callback_secret = CALLBACK_SECRET
    settings.firmar_mock_enabled = True
    settings.webhook_worker_enabled = False
    settings.trust_dir = str(settings.storage_dir) + "-sin-anclas"
    mock_firmar.reset()
    app.dependency_overrides[settings_dep] = lambda: settings
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.time() + 15
    while not server.started:
        assert time.time() < deadline
        time.sleep(0.05)
    yield base
    server.should_exit = True
    app.dependency_overrides.clear()
    mock_firmar.reset()


def test_flujo_por_http_real(live_server):
    headers = {"X-API-Key": DEMO_API_KEY}
    body = {"document_base64": b64(make_pdf()), "signer": SIGNER, "provider": "firmar"}
    created = httpx.post(f"{live_server}/api/v1/signature-requests", json=body, headers=headers).json()
    rid = created["id"]
    prepared_ = httpx.post(f"{live_server}/api/v1/signature-requests/{rid}/prepare", json={}, headers=headers, timeout=30)
    assert prepared_.status_code == 200, prepared_.text
    op = prepared_.json()["remote"]["operation_id"]
    token = httpx.post(
        f"{live_server}/mock/firmar/oauth/token",
        content=f"grant_type=client_credentials&client_id=firmadoc&client_secret={CLIENT_SECRET}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    ).json()["access_token"]
    approved = httpx.post(
        f"{live_server}/mock/firmar/v1/operations/{op}/approve",
        json={"otp": "123456", "pin": "1234"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    assert approved.status_code == 200 and approved.json()["callback_status"] == 200, approved.text
    final = httpx.get(f"{live_server}/api/v1/signature-requests/{rid}", headers=headers).json()
    assert final["status"] == "signed" and final["document"]["version_number"] == 2
    assert base64.b64decode(final["document"]["signed_document_base64"]).startswith(b"%PDF-")
