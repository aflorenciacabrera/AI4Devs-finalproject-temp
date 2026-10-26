"""Sello de tiempo (PAdES B-T): nivel, política ante fallos de la TSA, verificación y concurrencia."""

import asyncio
import base64
import datetime
import http.server
import io
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from asn1crypto import cms, keys, tsp
from asn1crypto import x509 as ax509
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from fastapi.testclient import TestClient
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.timestamps import DummyTimeStamper
from pyhanko_certvalidator.registry import SimpleCertificateStore
from sqlalchemy import select

from firmadoc import timestamping
from firmadoc.config import Settings
from firmadoc.main import app
from firmadoc.models import AuditEvent, SigningChallenge
from firmadoc.pdf_engine import verify_pdf

from .agent_simulator import AgentSimulator
from .test_flow import create, sign_fully
from .test_token_flow import prepare, signer_identity

DAY = datetime.timedelta(days=1)


def make_tsa(authority) -> tuple[ax509.Certificate, keys.PrivateKeyInfo, SimpleCertificateStore]:
    key = rsa.generate_private_key(65537, 2048)
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "TSA de Prueba")]))
        .issuer_name(authority.cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - 30 * DAY)
        .not_valid_after(now + 365 * DAY)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]), critical=True)
        .add_extension(
            x509.KeyUsage(True, True, False, False, False, False, False, False, False), critical=True
        )
        .sign(authority.key, hashes.SHA256())
    )
    tsa_cert = ax509.Certificate.load(cert.public_bytes(serialization.Encoding.DER))
    tsa_key = keys.PrivateKeyInfo.load(
        key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    store = SimpleCertificateStore()
    store.register(tsa_cert)
    return tsa_cert, tsa_key, store


class FlakyTimestamper(DummyTimeStamper):
    """TSA de prueba que puede "caerse"."""

    fail = False
    calls = 0

    async def async_request_tsa_response(self, req):
        type(self).calls += 1
        if self.fail:
            raise ConnectionError("TSA caida")
        return await super().async_request_tsa_response(req)


@pytest.fixture
def tsa(monkeypatch, pki, token_env):
    """TSA de confianza (cadena hasta la raíz de las anclas) conectada a Firmadoc."""
    cert, key, store = make_tsa(pki.ca)
    FlakyTimestamper.calls = 0
    stamper = FlakyTimestamper(cert, key, certs_to_embed=store)
    monkeypatch.setattr(timestamping, "make_timestamper", lambda settings: stamper)
    return stamper


def level_of(client, signed: dict) -> str:
    return signed["document"]["signature_level"]


def audit(session, request_id: str) -> dict[str, dict]:
    session.expire_all()
    rows = session.scalars(
        select(AuditEvent).where(AuditEvent.signature_request_id == uuid.UUID(request_id))
    ).all()
    return {e.event_type: e.payload for e in rows}


# --- configuración -----------------------------------------------------------------------------------


def test_url_de_tsa_invalida():
    for bad in ("ftp://tsa.example.org", "tsa.example.org", "file:///x"):
        with pytest.raises(ValueError):
            Settings(tsa_url=bad)
    assert Settings(tsa_url="").tsa_url is None
    assert Settings(tsa_url="http://tsa.example.org/ts").tsa_url


def test_sin_tsa_no_se_crea_sellador():
    assert timestamping.make_timestamper(Settings()) is None


# --- nivel y verificación -----------------------------------------------------------------------------


def test_sin_tsa_nivel_bb(client, session):
    signed = sign_fully(client)
    assert level_of(client, signed) == "B-B"
    assert audit(session, signed["id"])["signed"]["timestamp"] == {"status": "absent"}
    assert "timestamp_unavailable" not in audit(session, signed["id"])
    assert client.post(f"/api/v1/documents/{signed['document_id']}/verify").json()["signatures"][0]["timestamp"]["present"] is False


def test_con_tsa_nivel_bt(client, session, tsa):
    signed = sign_fully(client)
    assert level_of(client, signed) == "B-T"
    payload = audit(session, signed["id"])["signed"]
    assert payload["signature_level"] == "B-T" and payload["timestamp"] == {"status": "embedded"}
    assert tsa.calls == 1

    body = client.post(f"/api/v1/documents/{signed['document_id']}/verify").json()
    [sig] = body["signatures"]
    assert sig["timestamp"]["present"] and sig["timestamp"]["trusted"] and sig["timestamp"]["valid"]
    assert sig["timestamp"]["time"] and sig["ok"] and body["valid"] is True
    assert client.get(f"/api/v1/documents/{signed['document_id']}/signatures").status_code == 200


def test_tsa_desconocida_no_es_de_confianza(client, monkeypatch, pki, token_env):
    cert, key, store = make_tsa(pki.other_ca)  # cadena que no está en las anclas
    monkeypatch.setattr(timestamping, "make_timestamper", lambda s: DummyTimeStamper(cert, key, certs_to_embed=store))
    signed = sign_fully(client)
    body = client.post(f"/api/v1/documents/{signed['document_id']}/verify").json()
    [sig] = body["signatures"]
    assert sig["intact"] and sig["trusted"]  # la firma en sí es correcta
    assert sig["timestamp"]["present"] and sig["timestamp"]["trusted"] is False
    assert sig["ok"] is False and body["valid"] is False


def test_firma_con_sello_alterada_no_valida(client, tsa, settings):
    from pathlib import Path

    signed = sign_fully(client)
    stored = next(Path(settings.storage_dir).rglob("v2-*.pdf"))
    data = bytearray(stored.read_bytes())
    start = data.index(b"/Contents <") + len(b"/Contents <")
    data[start + 60] = ord("0") if data[start + 60] != ord("0") else ord("1")  # un nibble dentro del CMS
    stored.write_bytes(bytes(data))
    r = client.post(f"/api/v1/documents/{signed['document_id']}/verify")
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert r.json()["valid"] is False


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl no disponible")
def test_sello_verifica_con_openssl(client, tsa, pki, tmp_path):
    """Herramienta ajena a pyHanko: el sello incrustado se verifica con `openssl ts`."""
    signed = sign_fully(client)
    pdf = base64.b64decode(signed["document"]["signed_document_base64"])
    sig = PdfFileReader(io.BytesIO(pdf)).embedded_signatures[0]
    signer_info = cms.ContentInfo.load(sig.pkcs7_content.dump() if hasattr(sig.pkcs7_content, "dump") else sig.pkcs7_content)["content"]["signer_infos"][0]
    token = next(a for a in signer_info["unsigned_attrs"] if a["type"].native == "signature_time_stamp_token")["values"][0]
    (tmp_path / "token.der").write_bytes(token.dump())
    digest = __import__("hashlib").sha256(signer_info["signature"].native).hexdigest()
    (tmp_path / "root.pem").write_bytes(pki.root.pem)
    (tmp_path / "ca.pem").write_bytes(pki.ca.pem)
    out = subprocess.run(
        ["openssl", "ts", "-verify", "-in", str(tmp_path / "token.der"), "-token_in", "-digest", digest,
         "-CAfile", str(tmp_path / "root.pem"), "-untrusted", str(tmp_path / "ca.pem")],
        capture_output=True, text=True, check=False,
    )
    assert out.returncode == 0 and "Verification: OK" in out.stdout + out.stderr, out.stdout + out.stderr


# --- política ante la caída de la TSA -----------------------------------------------------------------


def test_tsa_caida_con_sello_opcional(client, session, tsa):
    tsa.fail = True
    signed = sign_fully(client)
    assert level_of(client, signed) == "B-B"
    events = audit(session, signed["id"])
    assert events["signed"]["timestamp"]["status"] == "unavailable"
    assert "TSA caida" in events["timestamp_unavailable"]["reason"]
    assert signed["status"] == "signed"


def test_tsa_caida_con_sello_obligatorio_se_puede_reintentar(client, session, tsa, settings):
    settings.tsa_required = True
    tsa.fail = True
    rid = create(client).json()["id"]
    assert client.post(f"/api/v1/signature-requests/{rid}/prepare", json={}).status_code == 200
    r = client.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})
    assert r.status_code == 503 and r.json()["code"] == "timestamp_unavailable"
    session.expire_all()
    challenge = session.scalar(select(SigningChallenge).where(SigningChallenge.signature_request_id == uuid.UUID(rid)))
    assert challenge.consumed_at is None  # no se gastó el desafío
    assert client.get(f"/api/v1/signature-requests/{rid}").json()["status"] == "signing"

    tsa.fail = False  # la TSA vuelve: se reintenta la misma firma
    again = client.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})
    assert again.status_code == 200 and again.json()["document"]["signature_level"] == "B-T"


def test_token_con_sello_obligatorio_no_pide_otra_firma(client, session, tsa, settings, pki):
    settings.tsa_required = True
    agent = AgentSimulator(signer_identity(pki))
    rid = create(client, provider="token").json()["id"]
    ch = prepare(client, rid, agent.certificate_pem).json()["challenges"][0]
    body = {"signatures": [{"challenge_id": ch["challenge_id"], "signature_base64": agent.sign(ch["hash_to_sign"])}]}
    tsa.fail = True
    assert client.post(f"/api/v1/signature-requests/{rid}/complete", json=body).status_code == 503
    tsa.fail = False
    ok = client.post(f"/api/v1/signature-requests/{rid}/complete", json=body)  # la misma firma, sin otro PIN
    assert ok.status_code == 200 and ok.json()["document"]["signature_level"] == "B-T"
    verify = client.post(f"/api/v1/documents/{ok.json()['document_id']}/verify").json()
    assert verify["valid"] is True and verify["signatures"][0]["timestamp"]["trusted"] is True


def test_dos_complete_simultaneos_con_tsa_dan_una_sola_version(client, session, tsa):
    rid = create(client).json()["id"]
    client.post(f"/api/v1/signature-requests/{rid}/prepare", json={})
    safe = TestClient(app, headers=client.headers, raise_server_exceptions=False)

    def attempt(_):
        return safe.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(r.status_code for r in pool.map(attempt, range(2)))
    assert codes.count(200) == 1
    versions = client.get(f"/api/v1/signature-requests/{rid}").json()["document"]["version_number"]
    assert versions == 2


# --- camino HTTP real ---------------------------------------------------------------------------------


@pytest.fixture
def http_tsa(pki, token_env):
    cert, key, store = make_tsa(pki.ca)
    dummy = DummyTimeStamper(cert, key, certs_to_embed=store)
    state = {"mode": "ok", "requests": 0}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            state["requests"] += 1
            if state["mode"] == "error":
                self.send_response(500)
                self.end_headers()
                return
            if state["mode"] == "garbage":
                self._reply(b"esto no es un sello")
                return
            if state["mode"] == "slow":
                time.sleep(2)
            response = asyncio.run(dummy.async_request_tsa_response(tsp.TimeStampReq.load(body)))
            self._reply(response.dump())

        def _reply(self, data: bytes):
            self.send_response(200)
            self.send_header("Content-Type", "application/timestamp-reply")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    token_env.tsa_url = f"http://127.0.0.1:{server.server_port}/tsa"
    token_env.tsa_timeout_seconds = 0.7
    yield state
    server.shutdown()
    server.server_close()


def test_http_real_exito(client, http_tsa, session):
    signed = sign_fully(client)
    assert level_of(client, signed) == "B-T" and http_tsa["requests"] == 1
    assert client.post(f"/api/v1/documents/{signed['document_id']}/verify").json()["valid"] is True


@pytest.mark.parametrize("mode", ["error", "garbage", "slow"])
def test_http_real_fallos_son_tsa_no_disponible(client, http_tsa, session, settings, mode):
    http_tsa["mode"] = mode
    signed = sign_fully(client)  # sello opcional: se firma sin sello
    assert level_of(client, signed) == "B-B"
    assert audit(session, signed["id"])["signed"]["timestamp"]["status"] == "unavailable"

    settings.tsa_required = True
    rid = create(client).json()["id"]
    client.post(f"/api/v1/signature-requests/{rid}/prepare", json={})
    r = client.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})
    assert r.status_code == 503 and r.json()["code"] == "timestamp_unavailable"


def test_verify_pdf_sin_sello_informa_ausencia(client):
    signed = sign_fully(client)
    pdf = base64.b64decode(signed["document"]["signed_document_base64"])
    [check] = verify_pdf(pdf, [], [])
    assert check.timestamp_present is False and check.timestamp_time is None and check.trusted is False
