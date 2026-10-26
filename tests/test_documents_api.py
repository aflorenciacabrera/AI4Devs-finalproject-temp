"""Estado del documento, listado de firmantes y verificación."""

import base64
import io
import shutil
import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pyhanko.pdf_utils.reader import PdfFileReader
from sqlalchemy import select

from firmadoc import integrators
from firmadoc.models import Document, SigningStatus

from .agent_simulator import AgentSimulator
from .test_flow import SIGNER, create, sign_fully
from .test_token_flow import run_token_flow, signer_identity

FUTURE = (datetime.now(UTC) + timedelta(days=7)).isoformat()


def new_document(client) -> str:
    return create(client).json()["document_id"]


def patch(client, document_id, **body):
    return client.patch(f"/api/v1/documents/{document_id}", json=body)


def sign_again(client, document_id) -> dict:
    created = client.post(
        "/api/v1/signature-requests",
        json={"document_id": document_id, "signer": SIGNER, "provider": "local"},
    ).json()
    rid = created["id"]
    assert client.post(f"/api/v1/signature-requests/{rid}/prepare", json={}).status_code == 200
    r = client.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})
    assert r.status_code == 200, r.text
    return r.json()


# --- estado y plazo ---------------------------------------------------------------------------------


def test_consultar_documento(client):
    document_id = new_document(client)
    r = client.get(f"/api/v1/documents/{document_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["signing_status"] == "draft" and body["signature_deadline"] is None
    assert body["deadline_passed"] is False and body["current_version_number"] == 1
    assert body["download_url"].endswith(f"/documents/{document_id}/versions/1/download")


def test_marcar_pendiente_y_volver_a_borrador(client):
    document_id = new_document(client)
    assert patch(client, document_id, signing_status="pending_signature").json()["signing_status"] == "pending_signature"
    assert patch(client, document_id, signing_status="draft").json()["signing_status"] == "draft"


@pytest.mark.parametrize("value", ["signed", "otra-cosa", None])
def test_estado_no_permitido(client, value):
    document_id = new_document(client)
    r = patch(client, document_id, signing_status=value)
    assert r.status_code == 422
    assert client.get(f"/api/v1/documents/{document_id}").json()["signing_status"] == "draft"


def test_firmado_no_vuelve_a_borrador_pero_si_a_pendiente(client):
    signed = sign_fully(client)
    document_id = signed["document_id"]
    assert client.get(f"/api/v1/documents/{document_id}").json()["signing_status"] == "signed"
    assert patch(client, document_id, signing_status="draft").status_code == 409
    assert client.get(f"/api/v1/documents/{document_id}").json()["signing_status"] == "signed"
    assert patch(client, document_id, signing_status="pending_signature").status_code == 200
    sign_again(client, document_id)  # otra ronda: al completarse vuelve a signed
    assert client.get(f"/api/v1/documents/{document_id}").json()["signing_status"] == "signed"


def test_plazo_se_fija_y_se_borra(client):
    document_id = new_document(client)
    r = patch(client, document_id, signature_deadline=FUTURE)
    assert r.status_code == 200 and r.json()["signature_deadline"] is not None
    assert r.json()["deadline_passed"] is False
    cleared = patch(client, document_id, signature_deadline=None)
    assert cleared.status_code == 200 and cleared.json()["signature_deadline"] is None


@pytest.mark.parametrize(
    "deadline",
    [
        (datetime.now(UTC) + timedelta(days=1)).replace(tzinfo=None).isoformat(),  # sin zona horaria
        (datetime.now(UTC) - timedelta(days=1)).isoformat(),  # pasada
    ],
)
def test_plazo_invalido(client, deadline):
    document_id = new_document(client)
    assert patch(client, document_id, signature_deadline=deadline).status_code == 422
    assert client.get(f"/api/v1/documents/{document_id}").json()["signature_deadline"] is None


def test_cuerpo_vacio(client):
    assert patch(client, new_document(client)).status_code == 422


def test_plazo_vencido_no_bloquea_la_firma(client, session):
    document_id = new_document(client)
    document = session.get(Document, uuid.UUID(document_id))
    document.signature_deadline = datetime.now(UTC) - timedelta(hours=1)
    session.commit()
    assert client.get(f"/api/v1/documents/{document_id}").json()["deadline_passed"] is True
    assert sign_again(client, document_id)["status"] == "signed"


def test_aislamiento_y_api_key(client, session):
    document_id = new_document(client)
    _system, key, _secret = integrators.create(session, "Otro", "")
    other = {"X-API-Key": key}
    paths = [("get", ""), ("get", "/signatures"), ("post", "/verify")]
    for method, suffix in paths:
        r = client.request(method, f"/api/v1/documents/{document_id}{suffix}", headers=other)
        assert r.status_code == 404, suffix
    assert client.patch(f"/api/v1/documents/{document_id}", json={"signing_status": "draft"}, headers=other).status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}", headers={"X-API-Key": "mala"}).status_code == 401
    assert client.get(f"/api/v1/documents/{uuid.uuid4()}").status_code == 404


# --- firmantes ----------------------------------------------------------------------------------------


def test_sin_firmas(client):
    assert client.get(f"/api/v1/documents/{new_document(client)}/signatures").json() == []


def test_dos_firmantes_en_orden(client):
    first = sign_fully(client)
    document_id = first["document_id"]
    sign_again(client, document_id)
    entries = client.get(f"/api/v1/documents/{document_id}/signatures").json()
    assert [e["version_number"] for e in entries] == [2, 3]
    assert all(e["signer_name"] == SIGNER["full_name"] and e["provider"] == "local" for e in entries)
    assert all(e["signed_at"] and e["certificate"]["serial_number"] for e in entries)


# --- verificación -------------------------------------------------------------------------------------


def verify(client, document_id):
    return client.post(f"/api/v1/documents/{document_id}/verify")


def test_verificar_documento_local(client):
    document_id = sign_fully(client)["document_id"]
    r = verify(client, document_id)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valid"] is True and body["hash_matches"] is True and body["version_number"] == 2
    [sig] = body["signatures"]
    assert sig["intact"] and sig["valid"] and sig["trusted"] and sig["ok"]


def test_verificar_dos_firmas(client):
    document_id = sign_fully(client)["document_id"]
    sign_again(client, document_id)
    body = verify(client, document_id).json()
    assert len(body["signatures"]) == 2 and body["valid"] is True
    assert all(s["ok"] for s in body["signatures"])  # la primera sigue válida tras la segunda


def test_verificar_documento_token(client, token_env, pki):
    agent = AgentSimulator(signer_identity(pki))
    _rid, r = run_token_flow(client, agent)
    body = verify(client, r.json()["document_id"]).json()
    assert body["valid"] is True and body["signatures"][0]["trusted"] is True


def test_ancla_desconocida_no_es_de_confianza(client, token_env, pki, tmp_path):
    agent = AgentSimulator(signer_identity(pki))
    _rid, r = run_token_flow(client, agent)
    document_id = r.json()["document_id"]
    empty = tmp_path / "sin-anclas"
    empty.mkdir()
    token_env.trust_dir = str(empty)
    body = verify(client, document_id).json()
    [sig] = body["signatures"]
    assert sig["intact"] and sig["valid"] and sig["trusted"] is False
    assert body["valid"] is False and body["hash_matches"] is True


def test_binario_alterado(client, settings):
    document_id = sign_fully(client)["document_id"]
    stored = next(Path(settings.storage_dir).rglob("v2-*.pdf"))
    data = bytearray(stored.read_bytes())
    data[100] ^= 0xFF  # un byte dentro del contenido firmado
    stored.write_bytes(bytes(data))
    r = verify(client, document_id)
    assert r.status_code == 200
    assert r.json()["hash_matches"] is False and r.json()["valid"] is False


def test_binario_alterado_solo_en_el_hash(client, settings):
    """Apéndice después del %%EOF: la firma original no cambia, pero el binario ya no es el registrado."""
    document_id = sign_fully(client)["document_id"]
    stored = next(Path(settings.storage_dir).rglob("v2-*.pdf"))
    stored.write_bytes(stored.read_bytes() + b"\n% apendice\n")
    body = verify(client, document_id).json()
    assert body["hash_matches"] is False and body["valid"] is False


def test_sin_firmas_no_es_valido(client):
    document_id = new_document(client)
    body = verify(client, document_id).json()
    assert body["signatures"] == [] and body["hash_matches"] is True and body["valid"] is False


def test_binario_ausente(client, settings):
    document_id = sign_fully(client)["document_id"]
    next(Path(settings.storage_dir).rglob("v2-*.pdf")).unlink()
    assert verify(client, document_id).status_code == 409


def test_documento_con_estado_actualizado_se_ve_en_la_base(client, session):
    document_id = new_document(client)
    patch(client, document_id, signing_status="pending_signature")
    session.expire_all()
    assert session.scalar(select(Document.signing_status).where(Document.id == uuid.UUID(document_id))) == SigningStatus.PENDING_SIGNATURE


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl no disponible")
def test_verificacion_coincide_con_openssl(client, tmp_path):
    """Herramienta ajena a pyHanko: la firma CMS del PDF que Firmadoc da por válido también verifica en openssl."""
    signed = sign_fully(client)
    document_id = signed["document_id"]
    assert verify(client, document_id).json()["valid"] is True
    pdf = base64.b64decode(signed["document"]["signed_document_base64"])
    sig = PdfFileReader(io.BytesIO(pdf)).embedded_signatures[0]
    a, b, c, d = (int(x) for x in sig.sig_object["/ByteRange"])
    (tmp_path / "content.bin").write_bytes(pdf[a : a + b] + pdf[c : c + d])
    (tmp_path / "sig.der").write_bytes(sig.pkcs7_content)
    out = subprocess.run(
        ["openssl", "cms", "-verify", "-binary", "-noverify", "-inform", "DER",
         "-in", str(tmp_path / "sig.der"), "-content", str(tmp_path / "content.bin"),
         "-out", str(tmp_path / "out.bin")],
        capture_output=True, text=True, check=False,
    )
    assert out.returncode == 0, out.stderr
