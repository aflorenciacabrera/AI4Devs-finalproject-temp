"""Pruebas del backend PKCS#11 contra SoftHSM. Se omiten si `SOFTHSM2_MODULE` no está definida."""

import base64
import hashlib
import os
from pathlib import Path

import pytest

import softhsm_support as hsm
from firmadoc_agent.errors import AgentError
from firmadoc_agent.pkcs11_backend import Pkcs11Backend
from firmadoc_agent.service import AgentService
from firmadoc_agent.testing import FakeUI
from helpers import make_cert

MODULE = os.environ.get("SOFTHSM2_MODULE")
pytestmark = pytest.mark.skipif(not MODULE, reason="SOFTHSM2_MODULE no definida (SoftHSM)")

LABEL = "Firmadoc Test"
LOCKED_LABEL = "Firmadoc Bloqueable"


@pytest.fixture(scope="module")
def identity(tmp_path_factory):
    """Dos tokens: uno normal (clave y certificado del usuario + AC) y otro para bloquearlo.

    Se inicializan los dos antes de cargar la biblioteca: SoftHSM no relee los slots después.
    """
    hsm.configure(tmp_path_factory.mktemp("softhsm"))
    hsm.init_token(LABEL)
    hsm.init_token(LOCKED_LABEL)
    _ca_key, ca_cert = make_cert("AC de Prueba", ca=True, cuil=None)
    key, cert = make_cert("Juan Perez")
    hsm.import_identity(MODULE, LABEL, b"", key, hsm.der(cert))
    hsm.import_ca(MODULE, LABEL, b"", hsm.der(ca_cert))
    locked_key, locked_cert = make_cert("Persona Bloqueable")
    hsm.import_identity(MODULE, LOCKED_LABEL, b"", locked_key, hsm.der(locked_cert))
    return key, cert


@pytest.fixture
def backend(identity):
    return Pkcs11Backend(MODULE)


@pytest.fixture
def cert_id(backend):
    return next(c.id for c in backend.list_certificates() if "Juan Perez" in c.subject)


def item(name, n):
    digest = hashlib.sha256(name.encode()).digest()
    return {
        "challenge_id": f"c{n}",
        "document_name": name,
        "hash_algorithm": "SHA-256",
        "hash_to_sign": base64.b64encode(digest).decode(),
    }, digest


def verify(cert, digest, signature):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, utils

    cert.public_key().verify(
        signature, digest, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256())
    )


def test_lista_el_certificado_de_usuario_y_omite_la_ac(backend, identity):
    certs = backend.list_certificates()
    assert sorted(c.token_label for c in certs) == sorted([LABEL, LOCKED_LABEL])  # dos tokens, sin las AC
    mine = next(c for c in certs if "Juan Perez" in c.subject)
    assert mine.token_label == LABEL
    assert mine.id.endswith(":01")
    assert mine.pem().startswith("-----BEGIN CERTIFICATE-----")
    assert all("AC de Prueba" not in c.subject for c in certs)


def test_firma_verificable_con_la_clave_publica(backend, identity, cert_id):
    _key, cert = identity
    _body, digest = item("a.pdf", 1)
    (signature,) = backend.sign(cert_id, hsm.USER_PIN, [digest])
    assert len(signature) == 256
    verify(cert, digest, signature)


def test_lote_de_tres_con_un_login(backend, identity, cert_id):
    _key, cert = identity
    digests = [item(f"doc-{i}.pdf", i)[1] for i in range(3)]
    signatures = backend.sign(cert_id, hsm.USER_PIN, digests)
    assert len(signatures) == 3
    for d, s in zip(digests, signatures, strict=True):
        verify(cert, d, s)


def test_pin_incorrecto_y_luego_correcto(backend, identity, cert_id):
    digest = item("a.pdf", 1)[1]
    with pytest.raises(AgentError) as e:
        backend.sign(cert_id, "0000", [digest])
    assert e.value.code == "pin_incorrect"
    # la sesión no quedó abierta ni autenticada: con el PIN correcto se firma
    assert len(backend.sign(cert_id, hsm.USER_PIN, [digest])) == 1


def test_muchas_firmas_seguidas_no_agotan_sesiones(backend, cert_id):
    digest = item("a.pdf", 1)[1]
    for _ in range(25):
        backend.sign(cert_id, hsm.USER_PIN, [digest])


def test_clave_privada_inexistente(backend, cert_id):
    serial = cert_id.rpartition(":")[0]
    with pytest.raises(AgentError) as e:
        backend.sign(f"{serial}:99", hsm.USER_PIN, [item("a.pdf", 1)[1]])
    assert e.value.code == "private_key_not_found"


def test_token_inexistente(backend):
    with pytest.raises(AgentError) as e:
        backend.sign("SERIE-INEXISTENTE:01", hsm.USER_PIN, [item("a.pdf", 1)[1]])
    assert e.value.code == "token_not_found"


def test_servicio_completo_sobre_softhsm(backend, identity, cert_id):
    _key, cert = identity
    ui = FakeUI(pin=hsm.USER_PIN)
    service = AgentService(backend, ui)
    items = [item(f"doc-{i}.pdf", i) for i in range(2)]
    result = service.sign({"certificate_id": cert_id, "items": [b for b, _ in items]})
    assert len(ui.prompts) == 1
    for (_, digest), sig in zip(items, result["signatures"], strict=True):
        verify(cert, digest, base64.b64decode(sig["signature_base64"]))


def test_cada_pin_incorrecto_baja_el_contador_del_token(identity):
    """SoftHSM marca USER_PIN_COUNT_LOW, pero no emula el bloqueo (de ese caso se ocupan los tests
    con un token falso en test_agent_pkcs11_mapping.py)."""
    from pkcs11 import TokenFlag

    backend = Pkcs11Backend(MODULE)
    locked_id = next(c.id for c in backend.list_certificates() if "Bloqueable" in c.subject)
    token = next(t for t in backend.tokens() if t.label.strip() == LOCKED_LABEL)
    assert not token.flags & TokenFlag.USER_PIN_COUNT_LOW
    with pytest.raises(AgentError) as e:
        backend.sign(locked_id, "0000", [item("a.pdf", 1)[1]])
    assert e.value.code == "pin_incorrect"
    token = next(t for t in backend.tokens() if t.label.strip() == LOCKED_LABEL)
    assert token.flags & TokenFlag.USER_PIN_COUNT_LOW


def test_modulo_inexistente(tmp_path):
    backend = Pkcs11Backend(str(Path(tmp_path) / "no-existe.so"))
    with pytest.raises(AgentError) as e:
        backend.list_certificates()
    assert e.value.code == "pkcs11_unavailable"
    assert "arquitectura" in e.value.detail


def test_modulo_sin_configurar():
    with pytest.raises(AgentError) as e:
        Pkcs11Backend(None).list_certificates()
    assert e.value.code == "pkcs11_unavailable"


def test_diagnostico_sobre_softhsm_lista_usuario_y_ac_sin_pin(backend, identity):
    from firmadoc_agent.config import AgentConfig
    from firmadoc_agent.diagnose import EXIT_OK, run_diagnose

    lines: list[str] = []
    code = run_diagnose(AgentConfig(pkcs11_module=MODULE), backend, lines.append)
    text = "\n".join(lines)
    assert code == EXIT_OK
    assert LABEL in text and "Juan Perez" in text
    assert "Certificado de usuario" in text and "Certificado de AC" in text
    assert "serialNumber del sujeto (CUIL): CUIL 20111111112" in text
    assert "initialized" in text.lower()  # indicadores del token


def test_autoprueba_sobre_softhsm(backend, identity, cert_id):
    from firmadoc_agent.selftest import self_test

    lines: list[str] = []
    assert self_test(backend, hsm.USER_PIN, cert_id, batch=3, out=lines.append)
    assert "\n".join(lines).count("OK: RSA PKCS#1 v1.5") == 3
