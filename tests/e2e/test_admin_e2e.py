"""Panel de administración en un Chrome real: ingreso, listado, texto hostil y confirmaciones."""

import base64

import httpx
import pytest
from sqlalchemy import select

from firmadoc.models import AdminEvent
from firmadoc.seed import DEMO_API_KEY

from ..pdfs import make_pdf

pytestmark = pytest.mark.e2e

TOKEN = "e2e-token-de-administracion-" + "x" * 20
HOSTILE = "<img src=x onerror=window.__pwned=1>Mallory"


def sign_local(live, full_name: str) -> str:
    signer = {"full_name": full_name, "identifier": "20999999990", "email": "m@example.org"}
    body = {"document_base64": base64.b64encode(make_pdf()).decode(), "external_document_id": "e2e-admin/1", "signer": signer, "provider": "local"}
    headers = {"X-API-Key": DEMO_API_KEY}
    created = httpx.post(f"{live.base}/api/v1/signature-requests", json=body, headers=headers).json()
    rid = created["id"]
    assert httpx.post(f"{live.base}/api/v1/signature-requests/{rid}/prepare", json={}, headers=headers).status_code == 200
    assert httpx.post(f"{live.base}/api/v1/signature-requests/{rid}/complete", json={}, headers=headers).status_code == 200
    return created["document_id"]


def login(page, live, token):
    page.goto(f"{live.base}/admin")
    page.fill("#token", token)
    page.click("#login-form button[type=submit]")


def test_token_invalido_no_ingresa(live, page):
    live.settings.admin_token = TOKEN
    login(page, live, "token-incorrecto-" + "y" * 30)
    page.wait_for_selector("#login-error:not([hidden])")
    assert "denegado" in page.inner_text("#login-error").lower()
    assert page.is_hidden("#app")
    assert page.evaluate("sessionStorage.getItem('firmadoc-admin-token')") is None


def test_ingreso_listado_y_texto_hostil(live, page):
    live.settings.admin_token = TOKEN
    sign_local(live, HOSTILE)
    login(page, live, TOKEN)
    page.wait_for_selector("#requests-table table tr:nth-child(2)")
    assert page.is_visible("#app")
    table = page.inner_text("#requests-table")
    assert "Mallory" in table and "<img" in table  # se muestra como texto
    assert page.evaluate("window.__pwned") is None  # y no se ejecutó
    assert page.locator("#requests-table img").count() == 0

    page.fill("#requests-filters input[name=signer]", "20999999990")
    page.click("#requests-filters button[type=submit]")
    page.locator("#requests-page", has_text="1 de 1").wait_for()


def test_custodia_desde_el_listado(live, page):
    live.settings.admin_token = TOKEN
    document_id = sign_local(live, "Persona Normal")
    login(page, live, TOKEN)
    page.wait_for_selector("#requests-table table tr:nth-child(2)")
    page.locator("#requests-table button", has_text="Ver custodia").first.click()
    page.wait_for_selector("#custody-result .card")
    assert document_id in page.inner_text("#custody-result") or "e2e-admin/1" in page.inner_text("#custody-result")


def test_rotar_pide_confirmacion(live, page):
    live.settings.admin_token = TOKEN
    login(page, live, TOKEN)
    page.wait_for_selector("#app:not([hidden])")
    page.click("nav button[data-tab=certificate]")
    page.wait_for_selector("#certificate-info .card")

    page.once("dialog", lambda d: d.dismiss())  # se cancela: no debe rotar
    page.click("#rotate")
    page.wait_for_timeout(500)
    assert live.session.scalars(select(AdminEvent)).first() is None

    page.once("dialog", lambda d: d.accept())
    page.click("#rotate")
    page.wait_for_selector("#message.ok")
    live.session.expire_all()
    assert live.session.scalars(select(AdminEvent)).first().action == "local_certificate_rotated"


def test_cerrar_sesion_borra_el_token(live, page):
    live.settings.admin_token = TOKEN
    login(page, live, TOKEN)
    page.wait_for_selector("#app:not([hidden])")
    assert page.evaluate("sessionStorage.getItem('firmadoc-admin-token')") == TOKEN
    page.click("#logout")
    assert page.evaluate("sessionStorage.getItem('firmadoc-admin-token')") is None
    assert page.is_visible("#login")
    assert page.context.cookies() == []  # no se usan cookies
