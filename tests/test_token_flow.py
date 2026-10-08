import base64
import datetime
import io
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from asn1crypto import pem
from asn1crypto import x509 as ax509
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext
from sqlalchemy import select

from firmadoc.models import (
    AuditEvent,
    Certificate,
    DocumentVersion,
    RequestStatus,
    RevocationStatus,
    SignatureRequest,
    SigningChallenge,
)

from .agent_simulator import AgentSimulator
from .pki import b64
from .test_flow import SIGNER, create, sign_fully

CUIL = SIGNER["identifier"]  # 20123456789
DAY = datetime.timedelta(days=1)


@pytest.fixture
def token_env(settings, pki, anchors, tmp_path):
    settings.trust_dir = str(anchors)
    settings.revocation_mode = "hard-fail"
    settings.revocation_fetch = False
    settings.crl_dir = str(tmp_path / "crl")
    pki.write_crls(Path(settings.crl_dir))
    return settings


def signer_identity(pki, **kw):
    return pki.ca.issue("Juan Pérez", CUIL, **kw)


def new_request(client, document_id=None):
    if document_id:
        body = {"document_id": document_id, "signer": SIGNER, "provider": "token"}
        return client.post("/api/v1/signature-requests", json=body).json()["id"]
    return create(client, provider="token").json()["id"]


def prepare(client, rid, cert_pem):
    return client.post(
        f"/api/v1/signature-requests/{rid}/prepare",
        json={"certificate_pem": cert_pem} if cert_pem is not None else {},
    )


def complete(client, rid, challenge_id, signature):
    return client.post(
        f"/api/v1/signature-requests/{rid}/complete",
        json={"signatures": [{"challenge_id": challenge_id, "signature_base64": signature}]},
    )


def run_token_flow(client, agent, document_id=None):
    rid = new_request(client, document_id)
    ch = prepare(client, rid, agent.certificate_pem).json()["challenges"][0]
    r = complete(client, rid, ch["challenge_id"], agent.sign(ch["hash_to_sign"]))
    return rid, r


def validate_all(pdf: bytes, pki, extra_roots=()) -> list[bool]:
    roots = [ax509.Certificate.load(pki.root.der)] + list(extra_roots)
    inter = [ax509.Certificate.load(pki.ca.der)]
    vc = ValidationContext(trust_roots=roots, other_certs=inter, allow_fetching=False)
    out = []
    for sig in PdfFileReader(io.BytesIO(pdf)).embedded_signatures:
        st = validate_pdf_signature(sig, vc)
        out.append(st.intact and st.valid and st.trusted)
    return out


# --- camino feliz ---------------------------------------------------------------------------


def test_flujo_token_de_punta_a_punta(client, session, token_env, pki):
    agent = AgentSimulator(signer_identity(pki))
    _rid, r = run_token_flow(client, agent)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "signed"
    assert body["provider"] == "token"
    assert body["document"]["version_number"] == 2
    assert body["document"]["is_active_version"] is True

    signed = base64.b64decode(body["document"]["signed_document_base64"])
    assert validate_all(signed, pki) == [True]

    # el servidor registró solo datos públicos del certificado y lo vinculó al firmante
    cert = session.scalar(
        select(Certificate).where(Certificate.serial_number == body["certificate"]["serial_number"])
    )
    assert cert.cuil == CUIL
    assert cert.revocation_status == RevocationStatus.GOOD
    assert cert.signer_id is not None

    d = client.get(f"/api/v1/documents/{body['document']['id']}/versions/2/download")
    assert d.content == signed


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl no disponible")
def test_flujo_token_verifica_con_openssl(client, token_env, pki, tmp_path):
    """Herramienta ajena a pyHanko: la firma CMS y la cadena del firmante se verifican con openssl."""
    agent = AgentSimulator(signer_identity(pki))
    _rid, r = run_token_flow(client, agent)
    signed = base64.b64decode(r.json()["document"]["signed_document_base64"])
    sig = PdfFileReader(io.BytesIO(signed)).embedded_signatures[0]
    a, b, c, d = (int(x) for x in sig.sig_object["/ByteRange"])
    (tmp_path / "content.bin").write_bytes(signed[a : a + b] + signed[c : c + d])
    (tmp_path / "sig.der").write_bytes(sig.pkcs7_content)
    (tmp_path / "root.pem").write_bytes(pki.root.pem)
    (tmp_path / "ca.pem").write_bytes(pki.ca.pem)
    (tmp_path / "signer.pem").write_text(agent.certificate_pem)

    cms = subprocess.run(
        [
            "openssl", "cms", "-verify", "-binary", "-noverify", "-inform", "DER",
            "-in", str(tmp_path / "sig.der"), "-content", str(tmp_path / "content.bin"),
            "-out", str(tmp_path / "out.bin"),
        ],
        capture_output=True, text=True, check=False,
    )
    assert cms.returncode == 0, cms.stderr
    assert "Verification successful" in cms.stderr + cms.stdout

    chain = subprocess.run(
        [
            "openssl", "verify", "-CAfile", str(tmp_path / "root.pem"),
            "-untrusted", str(tmp_path / "ca.pem"), str(tmp_path / "signer.pem"),
        ],
        capture_output=True, text=True, check=False,
    )
    assert chain.returncode == 0, chain.stderr + chain.stdout


def test_el_simulador_cumple_el_contrato(pki):
    """La firma del simulador es RSA PKCS#1 v1.5 sobre DigestInfo SHA-256 del hash."""
    from firmadoc.pdf_engine import verify_hash_signature

    ident = signer_identity(pki)
    digest = bytes(range(32))
    signature = base64.b64decode(AgentSimulator(ident).sign(b64(digest)))
    assert len(signature) == 256
    assert verify_hash_signature(ident.der, digest, signature)
    with pytest.raises(ValueError):
        AgentSimulator(ident).sign(b64(b"corto"))


# --- prepare: rechazos antes del PIN --------------------------------------------------------


def _expired(pki):
    now = datetime.datetime.now(datetime.UTC)
    return signer_identity(pki, not_before=now - 60 * DAY, not_after=now - DAY)


def _revoked(pki):
    ident = signer_identity(pki)
    pki.ca.revoke(ident)
    return ident


REJECTIONS = [
    ("otra_ac", lambda p: p.other_ca.issue("Juan", CUIL), 422, "certificate_untrusted"),
    ("vencido", _expired, 422, "certificate_expired"),
    ("revocado", _revoked, 422, "certificate_revoked"),
    ("cuil_ajeno", lambda p: p.ca.issue("Otra Persona", "20999999995"), 403, "cuil_mismatch"),
    ("sin_cuil", lambda p: p.ca.issue("Juan", None), 403, "cuil_mismatch"),
]


@pytest.mark.parametrize(("name", "make", "status", "code"), REJECTIONS, ids=[r[0] for r in REJECTIONS])
def test_prepare_rechaza_certificados(client, session, token_env, pki, name, make, status, code):
    ident = make(pki)
    pki.write_crls(Path(token_env.crl_dir))  # CRL con el certificado revocado, si corresponde
    rid = new_request(client)
    r = prepare(client, rid, ident.pem)
    assert r.status_code == status, r.text
    assert r.json()["code"] == code

    request = session.get(SignatureRequest, uuid.UUID(rid))
    session.refresh(request)
    assert request.status == RequestStatus.PENDING  # no cambia: se puede reintentar
    assert not session.scalars(
        select(SigningChallenge).where(SigningChallenge.signature_request_id == request.id)
    ).all()
    events = session.scalars(
        select(AuditEvent).where(AuditEvent.signature_request_id == request.id)
    ).all()
    rejected = [e for e in events if e.event_type == "rejected"]
    assert len(rejected) == 1 and rejected[0].payload["code"] == code


def test_prepare_sin_certificado(client, token_env):
    rid = new_request(client)
    r = prepare(client, rid, None)
    assert r.status_code == 422
    assert r.json()["code"] == "certificate_invalid"


def test_prepare_certificado_no_es_pem(client, token_env):
    rid = new_request(client)
    r = prepare(client, rid, "esto no es un certificado")
    assert r.status_code == 422
    assert r.json()["code"] == "certificate_invalid"


def test_tras_un_rechazo_se_puede_reintentar_con_otro_certificado(client, token_env, pki):
    rid = new_request(client)
    assert prepare(client, rid, pki.other_ca.issue("Juan", CUIL).pem).status_code == 422
    assert prepare(client, rid, signer_identity(pki).pem).status_code == 200


# --- complete: la firma y el certificado se verifican ------------------------------------


def _prepared(client, pki):
    ident = signer_identity(pki)
    agent = AgentSimulator(ident)
    rid = new_request(client)
    ch = prepare(client, rid, agent.certificate_pem).json()["challenges"][0]
    return rid, ch, agent


def _state(session, rid):
    request = session.get(SignatureRequest, uuid.UUID(rid))
    session.refresh(request)
    challenge = session.scalars(
        select(SigningChallenge).where(SigningChallenge.signature_request_id == request.id)
    ).one()
    session.refresh(challenge)
    versions = session.scalars(
        select(DocumentVersion).where(DocumentVersion.signature_request_id == request.id)
    ).all()
    return request, challenge, versions


def test_complete_sin_firma_no_consume_el_desafio(client, session, token_env, pki):
    rid, _ch, _agent = _prepared(client, pki)
    r = client.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})
    assert r.status_code == 422
    request, challenge, versions = _state(session, rid)
    assert challenge.consumed_at is None
    assert request.status == RequestStatus.SIGNING and not versions


def test_complete_firma_hecha_con_otra_clave(client, session, token_env, pki):
    rid, ch, _agent = _prepared(client, pki)
    impostor = AgentSimulator(signer_identity(pki))
    r = complete(client, rid, ch["challenge_id"], impostor.sign(ch["hash_to_sign"]))
    assert r.status_code == 422
    request, challenge, versions = _state(session, rid)
    assert request.status == RequestStatus.FAILED
    assert challenge.consumed_at is None
    assert not versions


def test_complete_firma_de_otro_hash(client, session, token_env, pki):
    rid, ch, agent = _prepared(client, pki)
    r = complete(client, rid, ch["challenge_id"], agent.sign(b64(bytes(32))))
    assert r.status_code == 422
    request, _challenge, versions = _state(session, rid)
    assert request.status == RequestStatus.FAILED and not versions


def test_complete_certificado_revocado_entre_prepare_y_complete(
    client, session, token_env, pki
):
    ident = signer_identity(pki)
    agent = AgentSimulator(ident)
    rid = new_request(client)
    ch = prepare(client, rid, agent.certificate_pem).json()["challenges"][0]
    pki.ca.revoke(ident)  # se revoca después de preparar
    pki.write_crls(Path(token_env.crl_dir))
    r = complete(client, rid, ch["challenge_id"], agent.sign(ch["hash_to_sign"]))
    assert r.status_code == 422
    assert r.json()["code"] == "certificate_revoked"
    request, challenge, versions = _state(session, rid)
    assert request.status == RequestStatus.FAILED
    assert challenge.consumed_at is None
    assert not versions


# --- varias firmas -------------------------------------------------------------------------


def test_firma_local_y_luego_token(client, token_env, pki):
    first = sign_fully(client)  # proveedor local
    doc_id = first["document"]["id"]
    agent = AgentSimulator(signer_identity(pki))
    _rid, r = run_token_flow(client, agent, document_id=doc_id)
    assert r.status_code == 200, r.text
    assert r.json()["document"]["version_number"] == 3
    signed = base64.b64decode(r.json()["document"]["signed_document_base64"])

    local_cert = ax509.Certificate.load(
        pem.unarmor((Path(token_env.local_cert_dir) / "demo-signer.crt").read_bytes())[2]
    )
    assert validate_all(signed, pki, extra_roots=[local_cert]) == [True, True]


def test_dos_firmantes_con_token(client, token_env, pki):
    first_agent = AgentSimulator(signer_identity(pki))
    _rid, r1 = run_token_flow(client, first_agent)
    doc_id = r1.json()["document"]["id"]
    _rid, r2 = run_token_flow(client, AgentSimulator(signer_identity(pki)), document_id=doc_id)
    assert r2.status_code == 200, r2.text
    signed = base64.b64decode(r2.json()["document"]["signed_document_base64"])
    assert validate_all(signed, pki) == [True, True]


# --- auditoría ------------------------------------------------------------------------------


def test_eventos_del_flujo_token(client, session, token_env, pki):
    ident = signer_identity(pki)
    agent = AgentSimulator(ident)
    rid = new_request(client)
    assert prepare(client, rid, pki.other_ca.issue("Juan", CUIL).pem).status_code == 422
    ch = prepare(client, rid, agent.certificate_pem).json()["challenges"][0]
    assert complete(client, rid, ch["challenge_id"], agent.sign(ch["hash_to_sign"])).status_code == 200
    body = client.get(f"/api/v1/signature-requests/{rid}").json()
    assert [e["event_type"] for e in body["events"]] == ["created", "rejected", "prepared", "signed"]
