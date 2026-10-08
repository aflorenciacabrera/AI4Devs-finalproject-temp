"""Webhooks al integrador: registro, firma, reintentos, SSRF, trabajador y CLI."""

import json
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar

import httpx
import pytest
from sqlalchemy import func, select

from firmadoc import integrators, webhooks
from firmadoc.models import (
    AuditEvent,
    DeliveryStatus,
    Document,
    IntegratingSystem,
    RequestStatus,
    SignatureRequest,
    WebhookDelivery,
)
from firmadoc.seed import DEMO_WEBHOOK_SECRET

from .test_flow import create, sign_fully

URL = "https://hooks.example.org/in"
PUBLIC = ["93.184.216.34"]


@pytest.fixture(autouse=True)
def public_resolver(monkeypatch):
    monkeypatch.setattr(webhooks, "RESOLVER", lambda host, port: PUBLIC)


def deliveries(session) -> list[WebhookDelivery]:
    session.expire_all()
    return list(session.scalars(select(WebhookDelivery).order_by(WebhookDelivery.created_at)))


def recorder(status: int = 200):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, content=b"no se lee")

    return httpx.MockTransport(handler), calls


def test_sin_callback_no_se_registra_entrega(client, session):
    sign_fully(client)
    assert deliveries(session) == []


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example.org/in",  # sin https
        "https://user:pw@hooks.example.org/in",  # credenciales
        "https:///sin-host",
        "ftp://hooks.example.org/in",
        "https://hooks.example.org:99999/in",  # puerto inválido
        "https://hooks.example.org/" + "a" * 2100,  # demasiado larga
    ],
)
def test_callback_invalido_se_rechaza_sin_crear_nada(client, session, url):
    r = create(client, callback_url=url)
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_callback_url"
    assert session.scalar(select(func.count()).select_from(SignatureRequest)) == 1  # solo la del seed
    assert session.scalar(select(func.count()).select_from(Document)) == 1


@pytest.mark.parametrize("address", ["127.0.0.1", "10.1.2.3", "192.168.0.5", "169.254.169.254", "::1", "::ffff:10.0.0.1", "fd00::1"])
def test_destinos_no_publicos_se_rechazan(client, monkeypatch, address):
    monkeypatch.setattr(webhooks, "RESOLVER", lambda host, port: [address])
    r = create(client, callback_url=URL)
    assert r.status_code == 422 and r.json()["code"] == "invalid_callback_url"


def test_un_destino_privado_entre_varios_basta_para_rechazar(client, monkeypatch):
    monkeypatch.setattr(webhooks, "RESOLVER", lambda host, port: ["93.184.216.34", "10.0.0.1"])
    assert create(client, callback_url=URL).status_code == 422


def test_host_que_no_resuelve_se_rechaza(client, monkeypatch):
    def boom(host, port):
        raise OSError("sin DNS")

    monkeypatch.setattr(webhooks, "RESOLVER", boom)
    assert create(client, callback_url=URL).status_code == 422


def test_firma_registra_entrega_en_la_misma_transaccion(client, session):
    result = sign_fully(client, callback_url=URL)
    [d] = deliveries(session)
    assert d.status == DeliveryStatus.PENDING and d.attempts == 0
    assert d.event_type == webhooks.EVENT_SIGNED and d.url == URL
    body = json.loads(d.body)
    assert body["event"] == "signature.signed"
    assert body["signature_request"]["id"] == result["id"]
    assert body["signature_request"]["status"] == "signed"
    assert body["document"]["version_number"] == 2
    assert body["document"]["is_active_version"] is True
    assert body["document"]["download_url"].endswith("/versions/2/download")
    assert "signed_document_base64" not in body["document"]
    assert body["certificate"]["subject"]


def test_entrega_exitosa_firma_el_cuerpo_y_audita(client, session, settings):
    sign_fully(client, callback_url=URL)
    transport, calls = recorder(204)
    assert webhooks.run_due(session, settings, transport=transport) == 1
    [call] = calls
    [d] = deliveries(session)
    assert d.status == DeliveryStatus.DELIVERED and d.attempts == 1 and d.response_status == 204
    assert d.next_attempt_at is None and d.last_error is None
    assert call.headers["X-Firmadoc-Event"] == "signature.signed"
    assert call.headers["X-Firmadoc-Delivery"] == str(d.id)
    assert webhooks.verify_signature(DEMO_WEBHOOK_SECRET, call.content, call.headers["X-Firmadoc-Signature"])
    assert call.content.decode() == d.body  # los mismos bytes registrados
    events = session.scalars(select(AuditEvent.event_type)).all()
    assert "webhook_delivered" in events
    assert webhooks.run_due(session, settings, transport=transport) == 0  # no se reenvía


def test_verify_signature_rechaza_alteraciones_y_vencidos():
    body = b'{"a":1}'
    header = webhooks.signature_header("s3cret", body, 1_000_000)
    assert webhooks.verify_signature("s3cret", body, header, now=1_000_010)
    assert not webhooks.verify_signature("s3cret", b'{"a":2}', header, now=1_000_010)
    assert not webhooks.verify_signature("otro", body, header, now=1_000_010)
    assert not webhooks.verify_signature("s3cret", body, header, now=1_000_000 + 301)  # vencida
    assert not webhooks.verify_signature("s3cret", body, "basura", now=1_000_000)


def test_reintentos_con_backoff_hasta_fallar(client, session, settings):
    sign_fully(client, callback_url=URL)
    transport, calls = recorder(500)
    now = datetime.now(UTC)
    for attempt, wait in enumerate(webhooks.BACKOFF_SECONDS, start=1):
        assert webhooks.run_due(session, settings, now=now, transport=transport) == 1
        [d] = deliveries(session)
        assert d.status == DeliveryStatus.PENDING and d.attempts == attempt
        assert d.last_error == "HTTP 500"
        due = d.next_attempt_at.replace(tzinfo=UTC)
        assert due == now + timedelta(seconds=wait)
        assert webhooks.run_due(session, settings, now=now, transport=transport) == 0  # aún no vence
        now = due
    assert webhooks.run_due(session, settings, now=now, transport=transport) == 1
    [d] = deliveries(session)
    assert d.status == DeliveryStatus.FAILED and d.attempts == webhooks.MAX_ATTEMPTS
    assert d.next_attempt_at is None
    assert len(calls) == webhooks.MAX_ATTEMPTS
    assert "webhook_failed" in session.scalars(select(AuditEvent.event_type)).all()
    assert len({c.content for c in calls}) == 1  # todos los intentos envían el mismo cuerpo


def test_redireccion_no_se_sigue(client, session, settings):
    sign_fully(client, callback_url=URL)
    transport, calls = recorder(302)
    webhooks.run_due(session, settings, transport=transport)
    [d] = deliveries(session)
    assert d.status == DeliveryStatus.PENDING and d.last_error == "HTTP 302" and len(calls) == 1


def test_error_de_red_no_filtra_la_url(client, session, settings):
    sign_fully(client, callback_url=URL)

    def boom(request):
        raise httpx.ConnectError("no conecta a https://hooks.example.org/in")

    webhooks.run_due(session, settings, transport=httpx.MockTransport(boom))
    [d] = deliveries(session)
    assert d.last_error == "ConnectError" and d.status == DeliveryStatus.PENDING


def test_ssrf_se_revalida_al_entregar(client, session, settings, monkeypatch):
    sign_fully(client, callback_url=URL)  # al crear, el host resolvía a una IP pública
    monkeypatch.setattr(webhooks, "RESOLVER", lambda host, port: ["10.0.0.9"])  # rebinding
    transport, calls = recorder()
    webhooks.run_due(session, settings, transport=transport)
    assert calls == []  # no se envió nada
    [d] = deliveries(session)
    assert d.last_error == "destino no permitido" and d.attempts == 1


def test_sin_secreto_la_entrega_falla_sin_enviar(client, session, settings):
    sign_fully(client, callback_url=URL)
    system = session.scalar(select(IntegratingSystem))
    system.webhook_secret = None
    session.commit()
    transport, calls = recorder()
    webhooks.run_due(session, settings, transport=transport)
    [d] = deliveries(session)
    assert calls == [] and d.status == DeliveryStatus.FAILED and d.last_error == "missing_secret"


def test_reserva_evita_doble_envio(client, session, settings):
    sign_fully(client, callback_url=URL)
    [d] = deliveries(session)
    now = datetime.now(UTC)
    d.next_attempt_at = now + timedelta(seconds=webhooks.LEASE_SECONDS)  # otro trabajador la reservó
    session.commit()
    transport, calls = recorder()
    assert webhooks.run_due(session, settings, now=now, transport=transport) == 0
    assert calls == []


def test_evento_de_fallo_incluye_el_codigo(client, session):
    from firmadoc.services.signature_flow import Ctx

    created = create(client, callback_url=URL).json()
    request = session.get(SignatureRequest, uuid.UUID(created["id"]))
    system = session.get(IntegratingSystem, request.integrating_system_id)
    ctx = Ctx(db=session, storage=None, settings=None, system=system)  # type: ignore[arg-type]
    request.status = RequestStatus.FAILED
    delivery = webhooks.enqueue(ctx, request, webhooks.EVENT_FAILED, error_code="certificate_revoked")
    session.commit()
    body = json.loads(delivery.body)
    assert body["event"] == "signature.failed" and body["error"] == {"code": "certificate_revoked"}
    assert "document" not in body


def test_migracion_no_afecta_solicitudes_sin_callback(client, session):
    created = create(client).json()
    session.expire_all()
    assert session.get(SignatureRequest, uuid.UUID(created["id"])).callback_url is None


# --- trabajador con servidor HTTP real -------------------------------------------------------------


class _Receiver(BaseHTTPRequestHandler):
    received: ClassVar[list[tuple[dict, bytes]]] = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        type(self).received.append((dict(self.headers), body))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def test_trabajador_entrega_a_un_servidor_real(client, session, settings, engine):
    from firmadoc.db import make_session_factory

    _Receiver.received = []
    server = HTTPServer(("127.0.0.1", 0), _Receiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        settings.webhook_allow_http = True
        settings.webhook_allow_private_hosts = True
        settings.webhook_poll_seconds = 0.05
        webhooks_resolver = webhooks.RESOLVER
        webhooks.RESOLVER = lambda host, port: ["127.0.0.1"]
        try:
            sign_fully(client, callback_url=f"http://127.0.0.1:{server.server_port}/hook")
            worker = webhooks.WebhookWorker(settings, make_session_factory(engine)).start()
            deadline = time.time() + 10
            while time.time() < deadline and not _Receiver.received:
                time.sleep(0.05)
            worker.stop()
            assert not worker.alive
        finally:
            webhooks.RESOLVER = webhooks_resolver
        [(headers, body)] = _Receiver.received
        assert webhooks.verify_signature(DEMO_WEBHOOK_SECRET, body, headers["X-Firmadoc-Signature"])
        [d] = deliveries(session)
        assert d.status == DeliveryStatus.DELIVERED
    finally:
        server.shutdown()


# --- CLI de integradores ------------------------------------------------------------------------


def test_cli_crea_sistema_con_clave_y_secreto(session, capsys):
    system, api_key, secret = integrators.create(session, "Gestor X", "https://gestor.example.org, http://localhost:4200")
    assert api_key.startswith("fdk_") and secret.startswith("whsec_")
    assert system.allowed_origins == "https://gestor.example.org,http://localhost:4200"
    assert system.api_key_hash == integrators.hash_api_key(api_key)
    assert api_key not in system.allowed_origins and system.api_key_hash != api_key  # solo se guarda el hash


@pytest.mark.parametrize("origins", ["gestor.example.org", "https://x.org/ruta", "javascript:alert(1)", "https://x.org*"])
def test_cli_rechaza_origenes_invalidos(session, origins):
    with pytest.raises(ValueError):
        integrators.create(session, "Malo", origins)


def test_cli_rota_el_secreto(session):
    system, _key, before = integrators.create(session, "Gestor Y", "")
    new = integrators.rotate_webhook_secret(session, system.name)
    assert new != before and new.startswith("whsec_")
    with pytest.raises(LookupError):
        integrators.rotate_webhook_secret(session, "inexistente")


def test_cli_rechaza_nombre_repetido(session):
    integrators.create(session, "Gestor Z", "")
    with pytest.raises(ValueError):
        integrators.create(session, "Gestor Z", "")


def test_cli_listado_no_imprime_secretos(session, capsys, monkeypatch):
    system, api_key, secret = integrators.create(session, "Gestor L", "")
    monkeypatch.setattr(integrators, "make_engine", lambda url: session.get_bind())
    integrators.main(["list"])
    out = capsys.readouterr().out
    assert "Gestor L" in out and secret not in out and api_key not in out and system.api_key_hash not in out


def test_rotacion_usa_el_secreto_nuevo_y_la_api_key_sigue_valiendo(client, session, settings):
    system = session.scalar(select(IntegratingSystem))
    new = integrators.rotate_webhook_secret(session, system.name)
    sign_fully(client, callback_url=URL)  # la API key demo sigue valiendo
    transport, calls = recorder()
    webhooks.run_due(session, settings, transport=transport)
    [call] = calls
    assert webhooks.verify_signature(new, call.content, call.headers["X-Firmadoc-Signature"])
    assert not webhooks.verify_signature(DEMO_WEBHOOK_SECRET, call.content, call.headers["X-Firmadoc-Signature"])


@pytest.mark.parametrize("address", ["100.64.0.1", "0.0.0.0", "224.0.0.1"])
def test_otros_rangos_no_publicos(client, monkeypatch, address):
    monkeypatch.setattr(webhooks, "RESOLVER", lambda host, port: [address])
    assert create(client, callback_url=URL).status_code == 422


def test_localhost_se_rechaza_con_el_resolvedor_real(client, monkeypatch):
    monkeypatch.setattr(webhooks, "RESOLVER", webhooks.default_resolver)
    assert create(client, callback_url="https://localhost/in").status_code == 422
    assert create(client, callback_url="https://127.0.0.1/in").status_code == 422


def test_tiempo_agotado_reintenta(client, session, settings):
    sign_fully(client, callback_url=URL)

    def slow(request):
        raise httpx.ReadTimeout("lento")

    webhooks.run_due(session, settings, transport=httpx.MockTransport(slow))
    [d] = deliveries(session)
    assert d.status == DeliveryStatus.PENDING and d.last_error == "ReadTimeout" and d.attempts == 1


def test_si_falla_el_registro_no_queda_firma_a_medias(client, session, monkeypatch):
    created = create(client, callback_url=URL).json()
    rid = created["id"]
    client.post(f"/api/v1/signature-requests/{rid}/prepare", json={})

    def boom(*args, **kwargs):
        raise RuntimeError("falla al registrar")

    monkeypatch.setattr(webhooks, "enqueue", boom)
    with pytest.raises(RuntimeError):
        client.post(f"/api/v1/signature-requests/{rid}/complete", json={"signatures": []})
    session.expire_all()
    request = session.get(SignatureRequest, uuid.UUID(rid))
    assert request.status == RequestStatus.SIGNING  # la firma no se confirmó
    assert deliveries(session) == []


def test_dos_ejecuciones_simultaneas_no_duplican_el_envio(client, settings, engine):
    from firmadoc.db import make_session_factory

    sign_fully(client, callback_url=URL)
    transport, calls = recorder()
    factory = make_session_factory(engine)
    barrier = threading.Barrier(2)

    def run():
        with factory() as db:
            barrier.wait()
            webhooks.run_due(db, settings, transport=transport)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1
