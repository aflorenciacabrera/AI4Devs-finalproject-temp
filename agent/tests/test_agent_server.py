import http.client
import json
import threading

import pytest

from conftest import hash_item
from firmadoc_agent.server import create_server
from firmadoc_agent.service import AgentService
from firmadoc_agent.testing import FakeUI, SoftwareBackend

ORIGIN = "https://firmadoc.example.org"


class Client:
    def __init__(self, port):
        self.port = port

    def request(
        self, method, path, *, headers=None, body=None, host=True, origin=ORIGIN, content_length=None
    ):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {} if headers is None else dict(headers)
        if origin:
            h.setdefault("Origin", origin)
        if isinstance(body, dict | list):
            h.setdefault("Content-Type", "application/json")
            body = json.dumps(body)
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        conn.putheader("Host", f"127.0.0.1:{self.port}" if host is True else host)
        for k, v in h.items():
            conn.putheader(k, v)
        data = body.encode() if isinstance(body, str) else body
        conn.putheader(
            "Content-Length", str(len(data or b"") if content_length is None else content_length)
        )
        conn.endheaders(data)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        payload = json.loads(raw) if raw else None
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, payload


@pytest.fixture
def make_server(token):
    servers = []

    def make(*, origins=(ORIGIN,), ui=None, backend=None):
        service = AgentService(backend or SoftwareBackend([token]), ui or FakeUI(pin="1234"))
        server = create_server(service, origins, port=0)
        threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True).start()
        servers.append(server)
        return server, Client(server.port)

    yield make
    for s in servers:
        s.shutdown()
        s.server_close()


@pytest.fixture
def api(make_server):
    return make_server()[1]


def sign_body(token, *items):
    return {"certificate_id": token.cert_id, "items": list(items)}


# --- interfaz y rutas -----------------------------------------------------------------------


def test_escucha_solo_en_loopback(make_server):
    server, _ = make_server()
    assert server.server_address[0] == "127.0.0.1"


def test_certificados_con_origen_permitido(api):
    status, headers, body = api.request("GET", "/certificates")
    assert status == 200
    assert headers["access-control-allow-origin"] == ORIGIN
    assert headers["x-firmadoc-agent"]
    assert body["certificates"][0]["certificate_pem"].startswith("-----BEGIN")


@pytest.mark.parametrize("path", ["/admin", "/", "/certificates/1", "/sign/x"])
def test_ruta_desconocida(api, path):
    status, _headers, body = api.request("GET", path)
    assert status == 404
    assert body["code"] == "not_found"


def test_metodo_no_permitido(api):
    assert api.request("POST", "/certificates", body={})[0] == 405
    assert api.request("GET", "/sign")[0] == 405
    assert api.request("PUT", "/sign", body={})[0] == 405
    assert api.request("DELETE", "/certificates")[0] == 405


# --- origen y host ------------------------------------------------------------------------


def test_origen_no_permitido(api):
    status, headers, body = api.request("GET", "/certificates", origin="https://evil.example.org")
    assert status == 403
    assert body["code"] == "origin_not_allowed"
    assert "access-control-allow-origin" not in headers


def test_pedido_sin_origin(api):
    status, _headers, body = api.request("GET", "/certificates", origin=None)
    assert (status, body["code"]) == (403, "origin_not_allowed")


def test_origen_null(api):
    assert api.request("GET", "/certificates", origin="null")[0] == 403


def test_el_origen_debe_coincidir_exactamente(api):
    for origin in [
        "http://firmadoc.example.org",  # otro esquema
        "https://firmadoc.example.org:8443",  # otro puerto
        "https://sub.firmadoc.example.org",  # otro host
        "https://firmadoc.example.org.evil.com",
    ]:
        assert api.request("GET", "/certificates", origin=origin)[0] == 403, origin


def test_lista_de_origenes_vacia_rechaza_todo(make_server):
    _, api = make_server(origins=())
    assert api.request("GET", "/certificates")[0] == 403


def test_host_ajeno_dns_rebinding(api):
    status, _headers, body = api.request("GET", "/certificates", host="evil.example.org:47123")
    assert (status, body["code"]) == (403, "host_not_allowed")


def test_host_localhost_permitido(api):
    port = api.port
    assert api.request("GET", "/certificates", host=f"localhost:{port}")[0] == 200


def test_rechazo_por_origen_no_toca_el_token(make_server, token):
    backend = SoftwareBackend([token])
    ui = FakeUI(pin="1234")
    _, api = make_server(backend=backend, ui=ui)
    api.request("POST", "/sign", body=sign_body(token, hash_item()), origin="https://evil.example.org")
    assert backend.login_attempts == 0 and ui.prompts == []


# --- preflight CORS y red privada --------------------------------------------------------


def test_preflight_de_red_privada(api):
    status, headers, _ = api.request(
        "OPTIONS",
        "/sign",
        headers={
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
            "Access-Control-Request-Private-Network": "true",
        },
    )
    assert status == 204
    assert headers["access-control-allow-origin"] == ORIGIN
    assert headers["access-control-allow-private-network"] == "true"
    assert "content-type" in headers["access-control-allow-headers"].lower()
    assert "POST" in headers["access-control-allow-methods"]


def test_preflight_sin_pedido_de_red_privada_no_la_anuncia(api):
    _, headers, _ = api.request("OPTIONS", "/certificates")
    assert "access-control-allow-private-network" not in headers


def test_preflight_de_origen_no_permitido(api):
    status, headers, _ = api.request(
        "OPTIONS",
        "/sign",
        origin="https://evil.example.org",
        headers={"Access-Control-Request-Private-Network": "true"},
    )
    assert status == 403
    assert not any(h.startswith("access-control-") for h in headers)


def test_nunca_se_responde_con_comodin(api):
    _, headers, _ = api.request("GET", "/certificates")
    assert headers["access-control-allow-origin"] != "*"


# --- formato del pedido ------------------------------------------------------------------


def test_sign_exige_content_type_json(api, token):
    status, _, _body = api.request(
        "POST", "/sign", body=json.dumps(sign_body(token, hash_item())),
        headers={"Content-Type": "text/plain"},
    )
    assert status == 415


def test_sign_cuerpo_malformado(api):
    status, headers, body = api.request(
        "POST", "/sign", body="{no es json", headers={"Content-Type": "application/json"}
    )
    assert (status, body["code"]) == (400, "invalid_request")
    assert headers["access-control-allow-origin"] == ORIGIN  # el widget puede leer el error


def test_sign_campos_faltantes(api):
    assert api.request("POST", "/sign", body={})[2]["code"] == "invalid_request"


def test_cuerpo_demasiado_grande(api):
    """Se rechaza por el encabezado, sin leer el cuerpo."""
    status, _, body = api.request(
        "POST",
        "/sign",
        body="{}",
        headers={"Content-Type": "application/json"},
        content_length=1024 * 1024 + 1,
    )
    assert (status, body["code"]) == (413, "payload_too_large")


def test_demasiados_elementos(api, token):
    items = [hash_item(f"d{i}.pdf", f"c{i}") for i in range(101)]
    status, _, body = api.request("POST", "/sign", body=sign_body(token, *items))
    assert (status, body["code"]) == (413, "too_many_items")


# --- firma por HTTP ---------------------------------------------------------------------


def test_firma_por_http(api, token):
    status, headers, body = api.request("POST", "/sign", body=sign_body(token, hash_item()))
    assert status == 200
    assert body["signatures"][0]["challenge_id"] == "c1"
    assert headers["access-control-allow-origin"] == ORIGIN


def test_usuario_cancela_por_http(make_server, token):
    _, api = make_server(ui=FakeUI(pin=None))
    status, _, body = api.request("POST", "/sign", body=sign_body(token, hash_item()))
    assert (status, body["code"]) == (409, "user_cancelled")


def test_pedido_concurrente_recibe_429(make_server, token):
    entered, release = threading.Event(), threading.Event()

    def hold():
        entered.set()
        release.wait(10)

    _server, api = make_server(ui=FakeUI(pin="1234", before_answer=hold))
    first = {}
    t = threading.Thread(
        target=lambda: first.update(r=api.request("POST", "/sign", body=sign_body(token, hash_item())))
    )
    t.start()
    assert entered.wait(5)
    status, _, body = api.request("POST", "/sign", body=sign_body(token, hash_item("b.pdf", "c2")))
    assert (status, body["code"]) == (429, "busy")
    release.set()
    t.join(10)
    assert first["r"][0] == 200


def test_error_interno_no_filtra_trazas(make_server, token):
    class Roto(SoftwareBackend):
        def list_certificates(self):
            raise RuntimeError("secreto interno C:\\ruta\\privada")

    _, api = make_server(backend=Roto([token]))
    status, _, body = api.request("GET", "/certificates")
    assert (status, body["code"]) == (500, "internal_error")
    assert "secreto" not in json.dumps(body)


def test_instancia_unica_por_puerto(make_server, token):
    server, _ = make_server()
    service = AgentService(SoftwareBackend([token]), FakeUI())
    with pytest.raises(OSError):
        create_server(service, (ORIGIN,), port=server.port)
