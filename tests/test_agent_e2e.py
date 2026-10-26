"""Punta a punta: servidor Firmadoc (API) + agente local real sobre HTTP, con una PKI de prueba.

El "widget" lo hace el test: habla con el agente por HTTP (como lo haría el navegador, con su
cabecera Origin) y con el servidor por su API.
"""

import base64
import http.client
import json
import threading
from dataclasses import dataclass

import pytest

from firmadoc_agent.server import create_server
from firmadoc_agent.service import AgentService
from firmadoc_agent.testing import FakeUI, SoftwareBackend, SoftwareToken

from .test_token_flow import complete, new_request, prepare, signer_identity, validate_all

WIDGET_ORIGIN = "https://firmadoc.example.org"


@dataclass
class Agent:
    server: object
    backend: SoftwareBackend
    ui: FakeUI
    identity: object

    def call(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=10)
        headers = {"Origin": WIDGET_ORIGIN}
        data = None
        if body is not None:
            data = json.dumps(body)
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        payload = json.loads(resp.read())
        conn.close()
        return resp.status, payload

    def certificates(self):
        status, body = self.call("GET", "/certificates")
        assert status == 200, body
        return body["certificates"]

    def sign(self, certificate_id, challenges):
        items = [
            {
                "challenge_id": c["challenge_id"],
                "document_name": c["document_name"],
                "hash_algorithm": c["hash_algorithm"],
                "hash_to_sign": c["hash_to_sign"],
            }
            for c in challenges
        ]
        return self.call("POST", "/sign", {"certificate_id": certificate_id, "items": items})


def start_agent(identity, pin="1234"):
    token = SoftwareToken("SERIE1:01", identity.der, identity.key)
    backend = SoftwareBackend([token], pin="1234")
    ui = FakeUI(pin=pin)
    server = create_server(AgentService(backend, ui), [WIDGET_ORIGIN], port=0)
    threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True).start()
    return Agent(server, backend, ui, identity)


@pytest.fixture
def agent_factory():
    started = []

    def make(identity, pin="1234"):
        a = start_agent(identity, pin)
        started.append(a)
        return a

    yield make
    for a in started:
        a.server.shutdown()
        a.server.server_close()


def widget_flow(client, agent):
    """Lo que hará el widget: listar → prepare → agente /sign → complete."""
    cert = agent.certificates()[0]
    rid = new_request(client)
    prep = prepare(client, rid, cert["certificate_pem"])
    return cert, rid, prep


def test_firma_de_punta_a_punta_con_el_agente(client, token_env, pki, agent_factory):
    agent = agent_factory(signer_identity(pki))
    cert, rid, prep = widget_flow(client, agent)
    assert prep.status_code == 200, prep.text
    challenges = prep.json()["challenges"]

    status, signed = agent.sign(cert["id"], challenges)
    assert status == 200, signed
    r = complete(client, rid, challenges[0]["challenge_id"], signed["signatures"][0]["signature_base64"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "signed"
    pdf = base64.b64decode(r.json()["document"]["signed_document_base64"])
    assert validate_all(pdf, pki) == [True]
    assert [p.document_names for p in agent.ui.prompts] == [[challenges[0]["document_name"]]]


def test_certificado_de_otra_ac_se_rechaza_antes_de_pedir_el_pin(client, token_env, pki, agent_factory):
    agent = agent_factory(pki.other_ca.issue("Juan Pérez", "20123456789"))
    _cert, _rid, prep = widget_flow(client, agent)
    assert prep.status_code == 422
    assert prep.json()["code"] == "certificate_untrusted"
    assert agent.ui.prompts == []  # nunca se mostró el diálogo ni se pidió el PIN
    assert agent.backend.login_attempts == 0


def test_cancelar_y_reintentar_con_el_mismo_desafio(client, token_env, pki, agent_factory):
    agent = agent_factory(signer_identity(pki), pin=None)  # el usuario cancela
    cert, rid, prep = widget_flow(client, agent)
    challenges = prep.json()["challenges"]
    status, body = agent.sign(cert["id"], challenges)
    assert (status, body["code"]) == (409, "user_cancelled")
    assert agent.backend.login_attempts == 0

    agent.ui.pin = "1234"  # reintenta: el desafío del servidor sigue vigente
    status, signed = agent.sign(cert["id"], challenges)
    assert status == 200
    r = complete(client, rid, challenges[0]["challenge_id"], signed["signatures"][0]["signature_base64"])
    assert r.status_code == 200 and r.json()["status"] == "signed"


def test_pin_incorrecto_un_intento_y_reintento_manual(client, token_env, pki, agent_factory):
    agent = agent_factory(signer_identity(pki), pin="0000")
    cert, rid, prep = widget_flow(client, agent)
    challenges = prep.json()["challenges"]
    status, body = agent.sign(cert["id"], challenges)
    assert (status, body["code"]) == (401, "pin_incorrect")
    assert agent.backend.login_attempts == 1  # el agente no reintentó por su cuenta

    agent.ui.pin = "1234"
    status, signed = agent.sign(cert["id"], challenges)
    assert status == 200
    r = complete(client, rid, challenges[0]["challenge_id"], signed["signatures"][0]["signature_base64"])
    assert r.status_code == 200


def test_lote_de_dos_documentos_con_un_solo_pin(client, token_env, pki, agent_factory):
    agent = agent_factory(signer_identity(pki))
    cert = agent.certificates()[0]

    requests, challenges = [], []
    for _ in range(2):
        rid = new_request(client)
        prep = prepare(client, rid, cert["certificate_pem"])
        assert prep.status_code == 200, prep.text
        requests.append(rid)
        challenges.append(prep.json()["challenges"][0])

    status, signed = agent.sign(cert["id"], challenges)  # un solo pedido, dos hashes
    assert status == 200, signed
    assert len(agent.ui.prompts) == 1  # una sola confirmación / un solo PIN
    assert len(agent.ui.prompts[0].document_names) == 2
    assert agent.backend.login_attempts == 1

    by_challenge = {s["challenge_id"]: s["signature_base64"] for s in signed["signatures"]}
    for rid, challenge in zip(requests, challenges, strict=True):
        r = complete(client, rid, challenge["challenge_id"], by_challenge[challenge["challenge_id"]])
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "signed"
