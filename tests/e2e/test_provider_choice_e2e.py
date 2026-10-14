"""Elección del método de firma en un Chrome real: token → demostración, y firma remota con el simulado."""

import base64
import re
import time

import httpx
import pytest

from firmadoc import mock_firmar, webhooks
from firmadoc.providers import firmar
from firmadoc.seed import DEMO_API_KEY

from ..pdfs import make_pdf
from ..test_flow import SIGNER
from ..test_token_flow import signer_identity
from .test_widget_e2e import SIGNED, choose_method, heading, open_widget, wait_for_message

pytestmark = pytest.mark.e2e

CLIENT_SECRET = "secreto-del-cliente-firmar"
CALLBACK_SECRET = "secreto-del-callback-" + "x" * 24


def create(live, provider, allowed):
    body = {
        "document_base64": base64.b64encode(make_pdf()).decode(),
        "external_document_id": "e2e-eleccion/1",
        "signer": SIGNER,
        "provider": provider,
        "allowed_providers": allowed,
    }
    r = httpx.post(f"{live.base}/api/v1/signature-requests", json=body, headers={"X-API-Key": DEMO_API_KEY})
    assert r.status_code == 201, r.text
    return r.json()


def test_sin_agente_se_elige_la_firma_de_demostracion(live, page):
    # no se inicia ningún agente: el token no está disponible y la persona cambia de método
    request = create(live, "token", ["token", "local"])
    widget = open_widget(page, live, request)
    heading(widget, "Elegí el método de firma").wait_for()
    choose_method(widget, "Firma con token")
    heading(widget, "No detectamos Firmadoc Agent").wait_for()

    widget.get_by_role("button", name="Elegir otro método").click()
    heading(widget, "Elegí el método de firma").wait_for()
    choose_method(widget, "Firma propia")
    heading(widget, "Firmar el documento").wait_for()
    widget.get_by_role("button", name="Firmar", exact=True).click()
    heading(widget, SIGNED).wait_for()

    assert wait_for_message(page, "firmadoc:signed")["document"]["version_number"] == 2
    final = live.get_request(request["id"])
    assert final["status"] == "signed" and final["provider"] == "local"
    kinds = [e["event_type"] for e in final["events"]]
    assert "provider_selected" in kinds


def test_firma_remota_desde_el_widget(live, page, monkeypatch):
    settings = live.settings
    settings.firmar_base_url = f"{live.base}/mock/firmar"
    settings.firmar_client_secret = CLIENT_SECRET
    settings.firmar_callback_secret = CALLBACK_SECRET
    settings.firmar_mock_enabled = True
    settings.webhook_worker_enabled = False
    mock_firmar.reset()
    monkeypatch.setattr(firmar, "TRANSPORT", None)
    monkeypatch.setattr(webhooks, "RESOLVER", lambda host, port: ["93.184.216.34"])

    request = create(live, "local", ["local", "firmar"])
    widget = open_widget(page, live, request)
    heading(widget, "Elegí el método de firma").wait_for()
    choose_method(widget, "Firma remota")
    heading(widget, "Firmar con el servicio de firma remota").wait_for()
    widget.get_by_role("button", name="Continuar", exact=True).click()
    heading(widget, "Esperando la firma en el servicio remoto").wait_for()

    link = widget.get_by_role("link", name="Continuar en el servicio de firma")
    href = link.get_attribute("href")
    assert href.startswith(f"{live.base}/mock/firmar/authorize/")

    # la persona autoriza en el servicio en una ventana emergente que abre el enlace (el sandbox del iframe
    # debe permitirlo), y ahí ingresa el OTP y el PIN
    with page.context.expect_page() as opened:
        link.click()
    service = opened.value
    service.wait_for_load_state()
    assert service.url == href
    service.fill("#otp", "123456")
    service.fill("#pin", "1234")
    service.get_by_role("button", name="Firmar", exact=True).click()
    service.locator(".msg.ok").wait_for(timeout=60_000)
    assert "Documento firmado" in service.locator(".msg.ok").inner_text()

    heading(widget, SIGNED).wait_for(timeout=20_000)
    # el widget cierra solo la ventana del servicio cuando la firma termina
    deadline = time.time() + 5
    while not service.is_closed() and time.time() < deadline:
        page.wait_for_timeout(100)
    assert service.is_closed()
    assert wait_for_message(page, "firmadoc:signed")["document"]["version_number"] == 2
    final = live.get_request(request["id"])
    assert final["status"] == "signed" and final["provider"] == "firmar"


def test_la_eleccion_muestra_el_documento_y_el_estado_del_agente(live, page, pki):
    live.start_agent(signer_identity(pki))
    request = create(live, "token", ["token", "local"])
    widget = open_widget(page, live, request)
    heading(widget, "Elegí el método de firma").wait_for()
    card = widget.get_by_label("Documento a firmar")
    card.wait_for()
    assert "e2e-eleccion_1.pdf" in card.inner_text() and "1 página" in card.inner_text()
    assert "pendiente de firma" in card.inner_text().lower()
    widget.get_by_text("Firmadoc Agent conectado · token detectado").wait_for()
    assert widget.get_by_role("radio", name=re.compile("Firma con token")).is_checked()
    assert widget.get_by_text("Firma digital").first.is_visible() and widget.get_by_text("Demostración").first.is_visible()
    widget.get_by_role("button", name="Firmar documento").click()
    heading(widget, "Elegí el certificado").wait_for()


def test_sin_agente_la_eleccion_lo_indica_sin_bloquear_otros_metodos(live, page):
    request = create(live, "token", ["token", "local"])  # no se inicia el agente
    widget = open_widget(page, live, request)
    heading(widget, "Elegí el método de firma").wait_for()
    widget.get_by_text("No detectamos Firmadoc Agent en esta PC").wait_for()
    choose_method(widget, "Firma propia")
    heading(widget, "Firmar el documento").wait_for()
