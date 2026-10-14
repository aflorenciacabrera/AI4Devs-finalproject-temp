"""Widget en un Chrome real: página anfitriona (otro origen) → iframe → servidor y agente reales."""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ..test_token_flow import _revoked, signer_identity, validate_all

pytestmark = pytest.mark.e2e

SIGNED = "Documento firmado correctamente"


def validate_in_thread(pdf: bytes, pki) -> list[bool]:
    """pyHanko usa asyncio.run: no puede correr en el hilo donde Playwright mantiene su event loop."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(validate_all, pdf, pki).result()


def widget_of(page, selector="iframe"):
    return page.frame_locator(selector)


def heading(frame, name):
    return frame.get_by_role("heading", name=name, level=1)


def host_messages(page) -> list[dict]:
    return page.evaluate("window.__messages")


def wait_for_message(page, message_type: str, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for entry in host_messages(page):
            if entry["data"].get("type") == message_type:
                return entry["data"]
        page.wait_for_timeout(100)
    raise AssertionError(f"la página anfitriona no recibió {message_type}: {host_messages(page)}")


def open_widget(page, live, request, mode="iframe", origin=None):
    page.goto(live.host_url(request["signing_url"], mode=mode, origin=origin))
    return widget_of(page, "firmadoc-widget iframe" if mode == "component" else "iframe")


def choose_method(widget, name: str) -> None:
    """Elige una tarjeta de método (por parte de su nombre) y confirma con «Firmar»."""
    widget.get_by_role("radio", name=re.compile(name)).check()
    widget.get_by_role("button", name="Firmar", exact=True).click()


def token_of(request) -> str:
    return request["signing_url"].partition("#t=")[2]


# --- firma con token ------------------------------------------------------------------------


def test_firma_con_token_dentro_del_iframe(live, page, pki, tmp_path):
    live.start_agent(signer_identity(pki))
    request = live.create_request("token")
    widget = open_widget(page, live, request)

    heading(widget, "Elegí el certificado").wait_for()
    assert wait_for_message(page, "firmadoc:ready")["requestId"] == request["id"]
    widget.get_by_role("button", name="Validar y continuar").click()
    heading(widget, SIGNED).wait_for()

    # la página anfitriona (otro origen) recibe el mensaje, sin recargarse y sin token ni PDF
    signed = wait_for_message(page, "firmadoc:signed")
    assert signed["document"]["version_number"] == 2
    assert signed["document"]["signature_level"] == "B-B"
    assert "token" not in str(signed).lower() and "base64" not in str(signed).lower()
    assert page.url.startswith(live.host_origin)

    # el servidor lo confirma (la verdad está en el servidor, no en el mensaje)
    assert live.get_request(request["id"])["status"] == "signed"

    # el PDF descargado desde el widget tiene una firma válida
    with page.expect_download() as download:
        widget.get_by_role("button", name="Descargar PDF firmado").click()
    path = Path(tmp_path) / "firmado.pdf"
    download.value.save_as(path)
    assert validate_in_thread(path.read_bytes(), pki) == [True]

    widget.get_by_role("button", name="Cerrar").click()
    wait_for_message(page, "firmadoc:closed")


def test_certificado_revocado_se_rechaza_antes_del_pin(live, page, pki):
    identity = _revoked(pki)
    pki.write_crls(Path(live.settings.crl_dir))
    agent = live.start_agent(identity)
    request = live.create_request("token")
    widget = open_widget(page, live, request)

    heading(widget, "Elegí el certificado").wait_for()
    widget.get_by_role("button", name="Validar y continuar").click()
    heading(widget, "El certificado no pudo validarse").wait_for()
    assert widget.locator(".reason").inner_text() == "Certificado revocado"
    assert widget.get_by_text("No se te pidió el PIN").first.is_visible()
    assert agent.ui.prompts == []  # nunca se mostró el diálogo ni se pidió el PIN
    assert live.get_request(request["id"])["status"] == "pending"


def test_agente_ausente_y_reintento_de_deteccion(live, page, pki):
    request = live.create_request("token")
    widget = open_widget(page, live, request)

    heading(widget, "No detectamos Firmadoc Agent").wait_for()
    assert widget.get_by_text("Firmadoc Agent instalado y en ejecución").is_visible()

    live.start_agent(signer_identity(pki))  # el agente se abre después
    widget.get_by_role("button", name="Reintentar detección").click()
    heading(widget, "Elegí el certificado").wait_for()


def test_sitio_no_autorizado_en_el_agente(live, page, pki):
    token = signer_identity(pki)
    import threading

    from firmadoc_agent.server import create_server
    from firmadoc_agent.service import AgentService
    from firmadoc_agent.testing import FakeUI, SoftwareBackend, SoftwareToken

    backend = SoftwareBackend([SoftwareToken("S:01", token.der, token.key)])
    server = create_server(AgentService(backend, FakeUI()), ["https://otro-sitio.example.org"], port=live.agent_port)
    threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True).start()
    try:
        widget = open_widget(page, live, live.create_request("token"))
        # El agente rechaza el origen con 403 SIN cabeceras CORS (no filtra nada): el navegador no deja
        # leer esa respuesta, así que el widget la ve como "agente no detectado" y lo explica en las
        # comprobaciones.
        heading(widget, "No detectamos Firmadoc Agent").wait_for()
        assert widget.get_by_text("Este sitio autorizado en el agente").is_visible()
    finally:
        server.shutdown()
        server.server_close()


def test_cancelar_en_el_agente_y_firmar_despues(live, page, pki):
    agent = live.start_agent(signer_identity(pki), user_pin=None)  # la persona cancela el diálogo
    request = live.create_request("token")
    widget = open_widget(page, live, request)

    heading(widget, "Elegí el certificado").wait_for()
    widget.get_by_role("button", name="Validar y continuar").click()
    widget.get_by_text("Cancelaste la firma en el agente").wait_for()
    assert agent.backend.login_attempts == 0

    agent.ui.pin = "1234"
    widget.get_by_role("button", name="Validar y continuar").click()
    heading(widget, SIGNED).wait_for()


def test_pin_incorrecto_un_solo_intento_y_reintento_manual(live, page, pki):
    agent = live.start_agent(signer_identity(pki), user_pin="0000")
    widget = open_widget(page, live, live.create_request("token"))

    heading(widget, "Elegí el certificado").wait_for()
    widget.get_by_role("button", name="Validar y continuar").click()
    heading(widget, "PIN incorrecto").wait_for()
    page.wait_for_timeout(500)
    assert agent.backend.login_attempts == 1  # ni el agente ni el widget reintentan solos

    agent.ui.pin = "1234"
    widget.get_by_role("button", name="Reintentar").click()
    heading(widget, SIGNED).wait_for()
    assert agent.backend.login_attempts == 2


# --- firma local y Web Component ------------------------------------------------------------


def test_firma_local_con_iframe(live, page):
    request = live.create_request("local")
    widget = open_widget(page, live, request)
    heading(widget, "Firmar el documento").wait_for()
    widget.get_by_role("button", name="Firmar", exact=True).click()
    heading(widget, SIGNED).wait_for()
    assert wait_for_message(page, "firmadoc:signed")["document"]["version_number"] == 2


def test_web_component_emite_eventos_dom(live, page):
    request = live.create_request("local")
    widget = open_widget(page, live, request, mode="component")
    heading(widget, "Firmar el documento").wait_for()
    widget.get_by_role("button", name="Firmar", exact=True).click()
    heading(widget, SIGNED).wait_for()

    deadline = time.time() + 10
    kinds: list[str] = []
    while time.time() < deadline and not any(k.startswith("evento DOM firmadoc-signed") for k in kinds):
        kinds = [m["kind"] for m in host_messages(page)]
        page.wait_for_timeout(100)
    assert "evento DOM firmadoc-ready" in kinds
    assert "evento DOM firmadoc-signed" in kinds


def test_firma_local_en_ventana_emergente(live, page):
    """Opción 3: la anfitriona abre la signing_url con window.open y el widget avisa por window.opener."""
    request = live.create_request("local")
    page.goto(live.host_url(request["signing_url"], mode="popup"))
    with page.context.expect_page() as opened:
        page.click("#open-popup")  # en un gesto del usuario, si no el navegador la bloquea
    popup = opened.value
    popup.wait_for_load_state()
    heading(popup, "Firmar el documento").wait_for()
    assert wait_for_message(page, "firmadoc:ready")["requestId"] == request["id"]
    popup.get_by_role("button", name="Firmar", exact=True).click()
    heading(popup, SIGNED).wait_for()
    assert wait_for_message(page, "firmadoc:signed")["document"]["version_number"] == 2

    popup.get_by_role("button", name="Cerrar", exact=True).click()  # avisa y cierra su propia ventana
    wait_for_message(page, "firmadoc:closed")
    deadline = time.time() + 5
    while not popup.is_closed() and time.time() < deadline:
        page.wait_for_timeout(100)
    assert popup.is_closed()
    wait_for_message(page, "popup:closed")  # la anfitriona detectó el cierre por popup.closed
    assert live.get_request(request["id"])["status"] == "signed"


# --- seguridad del embebido -----------------------------------------------------------------


def test_un_origen_no_permitido_no_puede_enmarcar_el_widget(live, page, pki):
    live.start_agent(signer_identity(pki))
    request = live.create_request("token")
    # 127.0.0.1 es otro origen que localhost: el integrador solo permite a localhost
    other_origin = f"http://127.0.0.1:{live.host_port}"
    page.goto(live.host_url(request["signing_url"], origin=other_origin))
    page.wait_for_timeout(2000)

    assert page.frame_locator("iframe").get_by_role("heading").count() == 0  # el widget no se mostró
    assert any("frame-ancestors" in message for message in page.console_messages), page.console_messages
    assert host_messages(page) == []  # y no recibió ningún mensaje del widget


def test_el_token_no_queda_en_la_url_el_almacenamiento_ni_la_consola(live, page, pki):
    live.start_agent(signer_identity(pki))
    request = live.create_request("token")
    secret = token_of(request)
    assert secret
    widget = open_widget(page, live, request)
    heading(widget, "Elegí el certificado").wait_for()
    widget.get_by_role("button", name="Validar y continuar").click()
    heading(widget, SIGNED).wait_for()

    frame = next(f for f in page.frames if f.url.startswith(f"{live.base}/sign/"))
    assert secret not in frame.url and "#t=" not in frame.url  # borrado de la barra de direcciones
    state = frame.evaluate("() => [localStorage.length, sessionStorage.length, document.cookie, location.href]")
    assert state[0] == 0 and state[1] == 0 and state[2] == ""
    assert secret not in state[3]
    assert not any(secret in message for message in page.console_messages)
