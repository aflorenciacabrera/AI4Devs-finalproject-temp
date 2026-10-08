import base64
import hashlib
import io
import shutil
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from asn1crypto import pem
from asn1crypto import x509 as ax509
from fastapi.testclient import TestClient
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext
from sqlalchemy import select, update

from firmadoc.main import app
from firmadoc.models import (
    AuditEvent,
    Document,
    DocumentVersion,
    IntegratingSystem,
    RequestStatus,
    SignatureRequest,
    SigningChallenge,
)
from firmadoc.seed import hash_api_key

from .pdfs import make_pdf

SIGNER = {"full_name": "Juan Pérez", "identifier": "20123456789", "email": "jperez@example.org"}


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def create(client, pdf: bytes | None = None, **extra):
    body = {
        "document_base64": b64(pdf or make_pdf()),
        "external_document_id": "exp-1/doc-1",
        "signer": SIGNER,
        "provider": "local",
        **extra,
    }
    return client.post("/api/v1/signature-requests", json=body)


def sign_fully(client, **create_extra) -> dict:
    created = create(client, **create_extra).json()
    rid = created["id"]
    assert client.post(f"/api/v1/signature-requests/{rid}/prepare", json={}).status_code == 200
    r = client.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})
    assert r.status_code == 200, r.text
    return r.json()


def independent_validation(pdf: bytes, settings) -> list[bool]:
    """Valida con la ruta de validación de pyHanko (distinta de la de firma)."""
    cert_pem = (Path(settings.local_cert_dir) / "demo-signer.crt").read_bytes()
    root = ax509.Certificate.load(pem.unarmor(cert_pem)[2])
    vc = ValidationContext(trust_roots=[root], allow_fetching=False)
    reader = PdfFileReader(io.BytesIO(pdf))
    results = []
    for sig in reader.embedded_signatures:
        status = validate_pdf_signature(sig, vc)
        results.append(status.intact and status.valid and status.trusted)
    return results


# --- autenticación -------------------------------------------------------------------------


def test_sin_api_key(client):
    r = TestClient(app).post("/api/v1/signature-requests", json={})
    assert r.status_code == 401


def test_api_key_invalida(client):
    r = TestClient(app, headers={"X-API-Key": "no-existe"}).get(
        f"/api/v1/signature-requests/{uuid.uuid4()}"
    )
    assert r.status_code == 401


# --- create --------------------------------------------------------------------------------


def test_create_documento_nuevo(client, session):
    r = create(client)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    base, _, fragment = body["signing_url"].partition("#t=")
    assert base == f"http://test/sign/{body['id']}"
    assert fragment  # el token del widget va en el fragmento
    versions = session.scalars(select(DocumentVersion)).all()
    mine = [v for v in versions if str(v.document_id) == body["document_id"]]
    assert [(v.version_number, v.origin.value) for v in mine] == [(1, "uploaded")]


def test_create_documento_existente_no_crea_version(client, session):
    first = create(client).json()
    r = client.post(
        "/api/v1/signature-requests",
        json={"document_id": first["document_id"], "signer": SIGNER, "provider": "local"},
    )
    assert r.status_code == 201
    assert r.json()["document_id"] == first["document_id"]
    versions = session.scalars(
        select(DocumentVersion).where(
            DocumentVersion.document_id == uuid.UUID(first["document_id"])
        )
    ).all()
    assert len(versions) == 1


def test_create_documento_de_otro_integrador(client, session):
    other = IntegratingSystem(name="otro", api_key_hash=hash_api_key("otra-key"))
    session.add(other)
    session.flush()
    doc = Document(integrating_system_id=other.id)
    session.add(doc)
    session.commit()
    r = client.post(
        "/api/v1/signature-requests",
        json={"document_id": str(doc.id), "signer": SIGNER, "provider": "local"},
    )
    assert r.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"document_base64": "esto-no-es-base64!!"},
        {"document_base64": b64(b"no soy un pdf")},
    ],
)
def test_create_archivo_invalido(client, payload):
    r = client.post(
        "/api/v1/signature-requests", json={"signer": SIGNER, "provider": "local", **payload}
    )
    assert r.status_code == 422


def test_create_demasiado_grande(client, settings):
    settings.max_document_bytes = 100
    assert create(client).status_code == 422


def test_create_exige_documento_o_id(client):
    r = client.post("/api/v1/signature-requests", json={"signer": SIGNER, "provider": "local"})
    assert r.status_code == 422


def test_create_proveedor_no_habilitado(client):
    r = create(client, provider="firmar")
    assert r.status_code == 422
    assert "habilitado" in r.json()["detail"]


def test_create_proveedor_token_habilitado(client):
    assert create(client, provider="token").status_code == 201


# --- flujo completo --------------------------------------------------------------------------


def test_flujo_local_de_punta_a_punta(client, session, settings):
    original = make_pdf()
    result = sign_fully(client, pdf=original)

    assert result["status"] == "signed"
    block = result["document"]
    assert block["version_number"] == 2
    assert block["is_active_version"] is True
    assert block["signing_status"] == "signed"
    assert block["signature_level"] == "B-B"
    assert result["certificate"]["serial_number"]

    signed = base64.b64decode(block["signed_document_base64"])
    assert independent_validation(signed, settings) == [True]

    # descargable y versionado a la vez; la versión 1 sigue intacta
    d = client.get(f"/api/v1/documents/{block['id']}/versions/2/download")
    assert d.status_code == 200
    assert d.headers["content-type"] == "application/pdf"
    assert d.content == signed
    v1 = client.get(f"/api/v1/documents/{block['id']}/versions/1/download")
    assert v1.content == original

    # hash coherente con el binario guardado
    versions = session.scalars(
        select(DocumentVersion).where(DocumentVersion.document_id == uuid.UUID(block["id"]))
    ).all()
    by_n = {v.version_number: v for v in versions}
    assert by_n[1].document_hash == hashlib.sha256(original).hexdigest()
    assert by_n[2].document_hash == hashlib.sha256(signed).hexdigest()
    doc = session.get(Document, uuid.UUID(block["id"]))
    session.refresh(doc)
    assert doc.current_version_id == by_n[2].id


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl no disponible")
def test_firma_verifica_con_openssl(client, tmp_path):
    """Verificación con una herramienta ajena a pyHanko: openssl cms -verify."""
    result = sign_fully(client)
    signed = base64.b64decode(result["document"]["signed_document_base64"])
    sig = PdfFileReader(io.BytesIO(signed)).embedded_signatures[0]
    a, b, c, d = (int(x) for x in sig.sig_object["/ByteRange"])
    (tmp_path / "content.bin").write_bytes(signed[a : a + b] + signed[c : c + d])
    (tmp_path / "sig.der").write_bytes(sig.pkcs7_content)
    out = subprocess.run(
        [
            "openssl", "cms", "-verify", "-binary", "-noverify", "-inform", "DER",
            "-in", str(tmp_path / "sig.der"), "-content", str(tmp_path / "content.bin"),
            "-out", str(tmp_path / "out.bin"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    assert "Verification successful" in out.stderr + out.stdout


def test_segunda_firma_genera_version_3(client, session, settings):
    first = sign_fully(client)
    doc_id = first["document"]["id"]
    second_req = client.post(
        "/api/v1/signature-requests",
        json={"document_id": doc_id, "signer": SIGNER, "provider": "local"},
    ).json()
    rid = second_req["id"]
    client.post(f"/api/v1/signature-requests/{rid}/prepare", json={})
    r = client.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})
    assert r.status_code == 200, r.text
    assert r.json()["document"]["version_number"] == 3
    signed3 = base64.b64decode(r.json()["document"]["signed_document_base64"])
    assert independent_validation(signed3, settings) == [True, True]  # la 1ª sigue válida
    v2 = client.get(f"/api/v1/documents/{doc_id}/versions/2/download").content
    assert v2 == base64.b64decode(first["document"]["signed_document_base64"])


def test_prepare_devuelve_desafio(client):
    rid = create(client).json()["id"]
    r = client.post(f"/api/v1/signature-requests/{rid}/prepare", json={})
    assert r.status_code == 200
    ch = r.json()["challenges"][0]
    assert ch["hash_algorithm"] == "SHA-256"
    assert len(base64.b64decode(ch["hash_to_sign"])) == 32
    assert ch["document_name"] == "exp-1_doc-1.pdf"


def test_get_solicitud_con_eventos_en_orden(client):
    result = sign_fully(client)
    r = client.get(f"/api/v1/signature-requests/{result['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["document"]["version_number"] == 2
    assert [e["event_type"] for e in body["events"]] == ["created", "prepared", "signed"]


def test_prepare_solicitud_ajena(client):
    assert client.post(f"/api/v1/signature-requests/{uuid.uuid4()}/prepare", json={}).status_code == 404


def test_prepare_estado_invalido(client):
    result = sign_fully(client)
    r = client.post(f"/api/v1/signature-requests/{result['id']}/prepare", json={})
    assert r.status_code == 409


def test_complete_sin_preparar(client):
    rid = create(client).json()["id"]
    r = client.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})
    assert r.status_code == 409


# --- desafíos -------------------------------------------------------------------------------


def _prepared(client):
    rid = create(client).json()["id"]
    ch = client.post(f"/api/v1/signature-requests/{rid}/prepare", json={}).json()["challenges"][0]
    return rid, ch


def test_desafio_vencido(client, session):
    rid, _ch = _prepared(client)
    session.execute(
        update(SigningChallenge).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    session.commit()
    r = client.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})
    assert r.status_code == 409
    versions = session.scalars(
        select(DocumentVersion).where(DocumentVersion.origin == "signed")
    ).all()
    assert all(v.signature_request_id != uuid.UUID(rid) for v in versions)


def test_desafio_reutilizado(client):
    rid, _ch = _prepared(client)
    assert client.post(f"/api/v1/signature-requests/{rid}/complete", json={}).status_code == 200
    # la solicitud ya está firmada: no se puede volver a completar
    r = client.post(f"/api/v1/signature-requests/{rid}/complete", json={})
    assert r.status_code == 409


def test_desafio_ya_consumido(client, session):
    rid, _ch = _prepared(client)
    session.execute(update(SigningChallenge).values(consumed_at=datetime.now(UTC)))
    session.commit()
    r = client.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})
    assert r.status_code == 409


def test_desafio_de_otra_sesion(client):
    rid, _ch = _prepared(client)
    r = client.post(
        f"/api/v1/signature-requests/{rid}/complete",
        json={"signatures": []},
        headers={"X-Session-Ref": "otra-sesion"},
    )
    assert r.status_code == 409


def test_desafio_inexistente_en_la_solicitud(client):
    rid, _ch = _prepared(client)
    r = client.post(
        f"/api/v1/signature-requests/{rid}/complete",
        json={"signatures": [{"challenge_id": str(uuid.uuid4()), "signature_base64": b64(b"x")}]},
    )
    assert r.status_code == 409


def test_firma_que_no_verifica_deja_la_solicitud_failed(client, session):
    rid, ch = _prepared(client)
    r = client.post(
        f"/api/v1/signature-requests/{rid}/complete",
        json={
            "signatures": [
                {"challenge_id": ch["challenge_id"], "signature_base64": b64(b"firma-falsa" * 30)}
            ]
        },
    )
    assert r.status_code == 422
    req = session.get(SignatureRequest, uuid.UUID(rid))
    session.refresh(req)
    assert req.status == RequestStatus.FAILED
    events = session.scalars(
        select(AuditEvent).where(AuditEvent.signature_request_id == req.id)
    ).all()
    assert "failed" in [e.event_type for e in events]
    # no se creó ninguna versión firmada
    assert not session.scalars(
        select(DocumentVersion).where(DocumentVersion.signature_request_id == req.id)
    ).all()


def test_dos_complete_simultaneos_solo_uno_gana(client, session):
    rid, _ch = _prepared(client)
    safe = TestClient(app, headers=client.headers, raise_server_exceptions=False)

    def attempt(_):
        return safe.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(r.status_code for r in pool.map(attempt, range(2)))
    assert codes.count(200) == 1
    session.expire_all()
    signed = session.scalars(
        select(DocumentVersion).where(DocumentVersion.signature_request_id == uuid.UUID(rid))
    ).all()
    assert len(signed) == 1


def test_orden_de_eventos_con_fallo(client, session):
    rid, ch = _prepared(client)
    client.post(
        f"/api/v1/signature-requests/{rid}/complete",
        json={"signatures": [{"challenge_id": ch["challenge_id"], "signature_base64": b64(b"x" * 256)}]},
    )
    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.signature_request_id == uuid.UUID(rid))
        .order_by(AuditEvent.created_at)
    ).all()
    assert [e.event_type for e in events] == ["created", "prepared", "failed"]
