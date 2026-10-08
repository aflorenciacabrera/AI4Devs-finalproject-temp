"""Sección «Firmar documento» del panel en un Chrome real: carga, widget embebido y firma."""

import re

import pytest
from sqlalchemy import select

from firmadoc.models import AdminEvent, Document, DocumentVersion

from ..pdfs import make_pdf
from .test_widget_e2e import SIGNED, choose_method, heading

pytestmark = pytest.mark.e2e

TOKEN = "e2e-token-de-administracion-" + "x" * 20
HOSTILE = "<img src=x onerror=window.__pwned=1>.pdf"


def open_sign_section(page, live):
    live.settings.admin_token = TOKEN
    page.goto(f"{live.base}/admin")
    page.fill("#token", TOKEN)
    page.click("#login-form button[type=submit]")
    page.wait_for_selector("#tab-sign:not([hidden])")  # es la sección inicial


def choose(page, name: str, data: bytes, mime="application/pdf"):
    page.set_input_files("#sign-file", files=[{"name": name, "mimeType": mime, "buffer": data}])


def test_cargar_y_firmar_con_el_widget_embebido(live, page):
    open_sign_section(page, live)
    choose(page, "Resolucion_0142-2026.pdf", make_pdf())
    page.wait_for_selector("#sign-ready:not([hidden])")
    assert page.inner_text("#sign-name") == "Resolucion_0142-2026.pdf"
    assert "1 página" in page.inner_text("#sign-meta")
    assert "versión original (v1)" in page.inner_text("#sign-versions")

    widget = page.frame_locator("#sign-widget iframe")
    heading(widget, "Elegí el método de firma").wait_for()
    choose_method(widget, "Firma propia")
    heading(widget, "Firmar el documento").wait_for()
    widget.get_by_role("button", name="Firmar", exact=True).click()
    heading(widget, SIGNED).wait_for()

    page.locator("#sign-result.ok").wait_for()
    assert "nueva versión vigente" in page.inner_text("#sign-result")
    live.session.expire_all()
    document = live.session.scalars(select(Document).order_by(Document.created_at.desc())).first()
    versions = list(
        live.session.scalars(
            select(DocumentVersion).where(DocumentVersion.document_id == document.id).order_by(DocumentVersion.version_number)
        )
    )
    assert [v.version_number for v in versions] == [1, 2]
    assert document.current_version_id == versions[1].id
    assert live.session.scalars(select(AdminEvent).where(AdminEvent.action == "panel_upload")).first() is not None


def test_quitar_vuelve_a_la_carga(live, page):
    open_sign_section(page, live)
    choose(page, "a.pdf", make_pdf())
    page.wait_for_selector("#sign-ready:not([hidden])")
    page.click("#sign-remove")
    assert page.is_visible("#sign-upload") and page.is_hidden("#sign-ready")
    assert page.locator("#sign-widget iframe").count() == 0


def test_archivo_que_no_es_pdf_no_se_envia(live, page):
    open_sign_section(page, live)
    requests = []
    page.on("request", lambda r: requests.append(r.url) if "signing-uploads" in r.url else None)
    choose(page, "notas.txt", b"hola", mime="text/plain")
    page.wait_for_selector("#message.bad")
    assert "PDF" in page.inner_text("#message")
    assert requests == [] and page.is_hidden("#sign-ready")


def test_nombre_de_archivo_hostil_se_muestra_como_texto(live, page):
    open_sign_section(page, live)
    choose(page, HOSTILE, make_pdf())
    page.wait_for_selector("#sign-ready:not([hidden])")
    assert "<img" in page.inner_text("#sign-name")
    assert page.locator("#sign-name img").count() == 0
    assert page.evaluate("window.__pwned") is None


def test_mensaje_de_otra_ventana_se_ignora(live, page):
    open_sign_section(page, live)
    choose(page, "a.pdf", make_pdf())
    page.wait_for_selector("#sign-ready:not([hidden])")
    # el propio panel (no el iframe) envía un «firmadoc:signed» falso: no es la ventana del widget
    page.evaluate("window.postMessage({source: 'firmadoc', type: 'firmadoc:signed'}, location.origin)")
    page.wait_for_timeout(300)
    assert page.is_hidden("#sign-result")


def choose_many(page, names, mime="application/pdf"):
    page.set_input_files(
        "#sign-file", files=[{"name": n, "mimeType": mime, "buffer": make_pdf(f"BT {n} ET".encode())} for n in names]
    )


def test_varios_pdf_se_firman_en_lote_con_el_widget(live, page):
    open_sign_section(page, live)
    choose_many(page, ["Providencia_0098.pdf", "Oficio_0231.pdf", "Dictamen_0177.pdf"])
    page.wait_for_selector("#sign-staged:not([hidden])")  # con varios se arma la lista antes de cargar
    assert page.locator("#sign-staged-list li").count() == 3
    page.locator("#sign-staged-list li", has_text="Oficio_0231.pdf").get_by_role("button", name="Quitar").click()
    assert page.locator("#sign-staged-list li").count() == 2
    choose_many(page, ["Oficio_0231.pdf"])  # se vuelve a agregar
    assert page.locator("#sign-staged-list li").count() == 3
    page.click("#sign-staged-go")

    page.wait_for_selector("#sign-ready:not([hidden])")
    assert page.inner_text("#sign-name") == "3 documentos"
    assert page.locator("#sign-docs li").count() == 3
    assert "1 página" in page.inner_text("#sign-docs")

    widget = page.frame_locator("#sign-widget iframe")
    heading(widget, "Elegí el método de firma").wait_for()
    widget.get_by_role("radio", name=re.compile("Firma propia")).check()
    widget.get_by_role("button", name="Firmar 3 documentos").click()
    heading(widget, "Firmar el documento").wait_for()
    widget.get_by_role("button", name="Firmar", exact=True).click()
    heading(widget, "Firma en lote completada").wait_for()

    page.locator("#sign-result.ok").wait_for()
    assert "3 de 3 documentos firmados" in page.inner_text("#sign-result")
    live.session.expire_all()
    assert live.session.scalars(select(AdminEvent).where(AdminEvent.action == "panel_batch_upload")).first() is not None


def test_varios_con_un_archivo_invalido_no_se_envia_nada(live, page):
    open_sign_section(page, live)
    sent = []
    page.on("request", lambda r: sent.append(r.url) if "signing-" in r.url else None)
    page.set_input_files(
        "#sign-file",
        files=[
            {"name": "a.pdf", "mimeType": "application/pdf", "buffer": make_pdf()},
            {"name": "notas.txt", "mimeType": "text/plain", "buffer": b"hola"},
        ],
    )
    page.wait_for_selector("#message.bad")
    assert "notas.txt" in page.inner_text("#message") and "PDF" in page.inner_text("#message")
    assert sent == [] and page.is_hidden("#sign-staged") and page.is_hidden("#sign-ready")


def test_el_servidor_rechaza_un_lote_demasiado_grande(live, page):
    live.settings.max_batch_size = 2
    open_sign_section(page, live)
    choose_many(page, ["a.pdf", "b.pdf", "c.pdf"])
    page.click("#sign-staged-go")
    page.wait_for_selector("#message.bad")
    assert "entre 2 y 2" in page.inner_text("#message")
    assert page.is_hidden("#sign-ready")  # quedan en la lista para quitar alguno
    assert page.locator("#sign-staged-list li").count() == 3


def test_mensaje_de_lote_de_otra_ventana_se_ignora(live, page):
    open_sign_section(page, live)
    choose_many(page, ["a.pdf", "b.pdf"])
    page.click("#sign-staged-go")
    page.wait_for_selector("#sign-ready:not([hidden])")
    page.evaluate(
        "window.postMessage({source: 'firmadoc', type: 'firmadoc:batch-completed', signed: 2, total: 2}, location.origin)"
    )
    page.wait_for_timeout(300)
    assert page.is_hidden("#sign-result")
