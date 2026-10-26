import base64
import threading

import pytest

from conftest import hash_item
from firmadoc_agent.backend import digest_info
from firmadoc_agent.errors import AgentError
from firmadoc_agent.service import AgentService
from firmadoc_agent.testing import FakeUI, SoftwareBackend
from helpers import ca_token, soft_token


def sign_body(token, *items):
    return {"certificate_id": token.cert_id, "items": list(items)}


def code_of(exc_info) -> str:
    return exc_info.value.code


# --- GET /certificates ----------------------------------------------------------------------


def test_lista_certificados_sin_pin(service, token, backend, ui):
    result = service.list_certificates()
    assert [c["id"] for c in result["certificates"]] == [token.cert_id]
    cert = result["certificates"][0]
    assert cert["certificate_pem"].startswith("-----BEGIN CERTIFICATE-----")
    assert "Juan Perez" in cert["subject"]
    assert backend.login_attempts == 0  # listar nunca pide PIN ni abre sesión
    assert ui.prompts == []
    assert result["agent_version"]


def test_los_certificados_de_ac_no_se_ofrecen():
    user, ca = soft_token(), ca_token()
    service = AgentService(SoftwareBackend([ca, user]), FakeUI())
    ids = [c["id"] for c in service.list_certificates()["certificates"]]
    assert ids == [user.cert_id]


def test_sin_token():
    service = AgentService(SoftwareBackend([]), FakeUI())
    with pytest.raises(AgentError) as e:
        service.list_certificates()
    assert code_of(e) == "token_not_found"


# --- POST /sign: camino feliz --------------------------------------------------------------


def test_lote_de_tres_con_un_solo_pin(service, token, backend, ui):
    items = [hash_item(f"doc-{i}.pdf", f"c{i}", bytes([i])) for i in range(3)]
    result = service.sign(sign_body(token, *items))

    assert len(ui.prompts) == 1  # el PIN se pide una sola vez
    assert ui.prompts[0].document_names == ["doc-0.pdf", "doc-1.pdf", "doc-2.pdf"]
    assert backend.login_attempts == 1
    assert backend.open_sessions == 0
    assert [s["challenge_id"] for s in result["signatures"]] == ["c0", "c1", "c2"]

    # cada firma es RSA PKCS#1 v1.5 sobre el DigestInfo del hash y verifica con la clave pública
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, utils

    public = SoftwareBackend.public_key(token)
    for item, sig in zip(items, result["signatures"], strict=True):
        digest = base64.b64decode(item["hash_to_sign"])
        public.verify(
            base64.b64decode(sig["signature_base64"]),
            digest,
            padding.PKCS1v15(),
            utils.Prehashed(hashes.SHA256()),
        )
        assert digest_info(digest).startswith(bytes.fromhex("3031300d06096086480165030402010500"))


def test_el_dialogo_muestra_el_certificado(service, token, ui):
    service.sign(sign_body(token, hash_item()))
    assert "Juan Perez" in ui.prompts[0].certificate_subject
    assert ui.prompts[0].last_try_warning is False


# --- cancelación y PIN -----------------------------------------------------------------------


def test_cancelar_no_abre_sesion(token, backend):
    service = AgentService(backend, FakeUI(pin=None))
    with pytest.raises(AgentError) as e:
        service.sign(sign_body(token, hash_item()))
    assert code_of(e) == "user_cancelled"
    assert backend.login_attempts == 0


def test_pin_vacio_equivale_a_cancelar(token, backend):
    service = AgentService(backend, FakeUI(pin=""))
    with pytest.raises(AgentError) as e:
        service.sign(sign_body(token, hash_item()))
    assert code_of(e) == "user_cancelled"
    assert backend.login_attempts == 0


def test_pin_incorrecto_un_unico_intento(token, backend):
    service = AgentService(backend, FakeUI(pin="9999"))
    with pytest.raises(AgentError) as e:
        service.sign(sign_body(token, hash_item("a.pdf"), hash_item("b.pdf", "c2")))
    assert code_of(e) == "pin_incorrect"
    assert e.value.status == 401
    assert backend.login_attempts == 1  # el agente no reintenta por su cuenta
    assert backend.sign_calls == 0
    assert backend.open_sessions == 0


def test_pin_bloqueado(token):
    backend = SoftwareBackend([token], pin="1234", retries=1)
    service = AgentService(backend, FakeUI(pin="0000"))
    with pytest.raises(AgentError) as e:
        service.sign(sign_body(token, hash_item()))
    assert code_of(e) == "pin_locked"
    assert e.value.status == 423


def test_ultimo_intento_se_advierte_en_el_dialogo(token):
    backend = SoftwareBackend([token], pin="1234", retries=1)
    ui = FakeUI(pin="1234")
    AgentService(backend, ui).sign(sign_body(token, hash_item()))
    assert ui.prompts[0].last_try_warning is True


# --- validación del pedido ------------------------------------------------------------------


def _bad(**override):
    item = hash_item()
    item.update(override)
    return item


@pytest.mark.parametrize(
    "item",
    [
        _bad(hash_algorithm="SHA-512"),
        _bad(hash_algorithm=None),
        _bad(hash_to_sign=base64.b64encode(b"corto").decode()),
        _bad(hash_to_sign="no-es-base64!!"),
        _bad(document_name=""),
        _bad(document_name="   "),
        _bad(document_name="x" * 300),
        _bad(challenge_id=""),
    ],
)
def test_pedido_invalido_no_muestra_dialogo(token, backend, ui, item):
    service = AgentService(backend, ui)
    with pytest.raises(AgentError) as e:
        service.sign(sign_body(token, item))
    assert code_of(e) == "invalid_request"
    assert ui.prompts == [] and backend.login_attempts == 0


@pytest.mark.parametrize("body", [None, [], "texto", {}, {"certificate_id": "a1b2"}, {"items": []}])
def test_cuerpo_invalido(service, body):
    with pytest.raises(AgentError) as e:
        service.sign(body)
    assert code_of(e) == "invalid_request"


def test_demasiados_elementos(service, token):
    items = [hash_item(f"d{i}.pdf", f"c{i}") for i in range(101)]
    with pytest.raises(AgentError) as e:
        service.sign(sign_body(token, *items))
    assert code_of(e) == "too_many_items"
    assert e.value.status == 413


def test_certificado_inexistente(service, ui):
    with pytest.raises(AgentError) as e:
        service.sign({"certificate_id": "ffff", "items": [hash_item()]})
    assert code_of(e) == "certificate_not_found"
    assert ui.prompts == []


def test_los_caracteres_de_control_del_nombre_se_limpian(service, token, ui):
    service.sign(sign_body(token, hash_item("doc\r\n\x1b[2Jmalo.pdf")))
    assert "\n" not in ui.prompts[0].document_names[0]
    assert "\x1b" not in ui.prompts[0].document_names[0]


# --- errores a mitad del lote y concurrencia -------------------------------------------------


def test_error_a_mitad_de_lote_sin_firmas_parciales(token, backend):
    backend.fail_at_index = 1
    service = AgentService(backend, FakeUI(pin="1234"))
    items = [hash_item(f"d{i}.pdf", f"c{i}", bytes([i])) for i in range(3)]
    with pytest.raises(AgentError):
        service.sign(sign_body(token, *items))
    assert backend.open_sessions == 0  # la sesión se cerró
    assert backend.sign_calls == 1  # se firmó solo el primero y no se devolvió nada


def test_segundo_pedido_mientras_hay_un_dialogo_abierto_recibe_busy(token, backend):
    entered, release = threading.Event(), threading.Event()
    result = {}

    def hold():
        entered.set()
        release.wait(5)

    service = AgentService(backend, FakeUI(pin="1234", before_answer=hold))
    first = threading.Thread(
        target=lambda: result.update(first=service.sign(sign_body(token, hash_item())))
    )
    first.start()
    assert entered.wait(5)
    with pytest.raises(AgentError) as e:
        service.sign(sign_body(token, hash_item("otro.pdf", "c9")))
    assert code_of(e) == "busy"
    assert e.value.status == 429
    release.set()
    first.join(5)
    assert "first" in result  # el primero no se vio afectado
