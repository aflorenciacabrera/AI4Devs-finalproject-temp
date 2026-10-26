"""Documentos, detalle de custodia e Integradores del panel en un Chrome real."""

import base64
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from firmadoc.seed import DEMO_API_KEY

from ..pdfs import make_pdf
from ..test_flow import SIGNER
from .test_admin_e2e import HOSTILE, TOKEN, login, sign_local

pytestmark = pytest.mark.e2e

H = {"X-API-Key": DEMO_API_KEY}


def sign_local_batch(live, n=2) -> str:
    body = {
        "documents": [
            {"document_base64": base64.b64encode(make_pdf(f"BT {i} ET".encode())).decode(), "external_document_id": f"lote-e2e/{i}"}
            for i in range(n)
        ],
        "signer": SIGNER,
        "provider": "local",
    }
    created = httpx.post(f"{live.base}/api/v1/signature-batches", json=body, headers=H).json()
    assert httpx.post(f"{live.base}/api/v1/signature-batches/{created['id']}/prepare", json={}, headers=H).status_code == 200
    assert httpx.post(f"{live.base}/api/v1/signature-batches/{created['id']}/complete", json={}, headers=H).status_code == 200
    return created["id"]


def pending_with_deadline(live) -> None:
    body = {"document_base64": base64.b64encode(make_pdf()).decode(), "external_document_id": "pendiente-e2e", "signer": SIGNER, "provider": "local"}
    created = httpx.post(f"{live.base}/api/v1/signature-requests", json=body, headers=H).json()
    deadline = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    r = httpx.patch(
        f"{live.base}/api/v1/documents/{created['document_id']}",
        json={"signing_status": "pending_signature", "signature_deadline": deadline},
        headers=H,
    )
    assert r.status_code == 200, r.text


def open_documents(page, live):
    live.settings.admin_token = TOKEN
    login(page, live, TOKEN)
    page.click(".sidebar button[data-tab=documents]")
    page.wait_for_selector("#requests-table table tr:nth-child(2)")


def test_la_navegacion_lateral_cambia_de_seccion(live, page):
    live.settings.admin_token = TOKEN
    login(page, live, TOKEN)
    page.wait_for_selector("#app:not([hidden])")
    assert page.locator(".sidebar button").all_inner_texts() == [
        "Firmar documento", "Documentos", "Auditoría", "Integradores", "Confianza",
    ]
    for tab in ("integrators", "trust", "audit", "documents", "sign"):
        page.click(f".sidebar button[data-tab={tab}]")
        assert page.is_visible(f"#tab-{tab}")
        assert page.get_attribute(f".sidebar button[data-tab={tab}]", "aria-current") == "true"
    page.click(".sidebar button[data-tab=trust]")
    assert page.is_visible("#anchors-table") and page.is_visible("#certificate-info")  # Confianza agrupa ambas
    page.click(".sidebar button[data-tab=audit]")
    assert page.is_visible("#webhooks-table") and page.is_visible("#events-table")


def test_origen_vencimiento_estado_y_filtros(live, page):
    sign_local(live, "Persona Individual")
    sign_local_batch(live, 2)
    pending_with_deadline(live)
    open_documents(page, live)
    table = page.inner_text("#requests-table")
    assert "Individual" in table and "Lote #" in table and "Firmado" in table
    assert "Pendiente" in table and "Vence" in table
    assert page.locator("#requests-table .chip.signed").count() >= 3 and page.locator("#requests-table .chip.pending").count() == 1

    page.select_option("#requests-filters select[name=origin]", "batch")
    page.click("#requests-filters button[type=submit]")
    page.locator("#requests-page", has_text="1-2 de 2").wait_for()
    rows = page.locator("#requests-table tbody tr, #requests-table tr:not(:first-child)")
    assert all("Lote #" in t for t in rows.all_inner_texts())

    page.select_option("#requests-filters select[name=origin]", "")
    page.fill("#requests-filters input[name=q]", "pendiente-e2e")
    page.click("#requests-filters button[type=submit]")
    page.locator("#requests-page", has_text="1-1 de 1").wait_for()


def test_las_filas_de_un_lote_se_ven_juntas_y_con_la_misma_etiqueta(live, page):
    sign_local_batch(live, 3)
    sign_local(live, "Posterior")
    open_documents(page, live)
    labels = [t for t in page.locator("#requests-table tr td:nth-child(5)").all_inner_texts()]
    batch_positions = [i for i, t in enumerate(labels) if t.startswith("Lote #")]
    assert len(batch_positions) == 3 and batch_positions == list(range(batch_positions[0], batch_positions[0] + 3))
    assert len({labels[i] for i in batch_positions}) == 1


def test_el_texto_hostil_del_listado_y_del_detalle_se_muestra_como_texto(live, page):
    sign_local(live, HOSTILE)
    open_documents(page, live)
    assert "<img" in page.inner_text("#requests-table")
    page.locator("#requests-table button", has_text="Ver detalle").first.click()
    page.wait_for_selector("#document-detail .timeline li")
    assert page.evaluate("window.__pwned") is None
    assert page.locator("#document-detail img").count() == 0 and page.locator("#requests-table img").count() == 0


def test_el_detalle_muestra_la_historia_las_versiones_y_descarga_la_v1(live, page, tmp_path):
    sign_local(live, "Persona Normal")
    open_documents(page, live)
    page.locator("#requests-table button", has_text="Ver detalle").first.click()
    page.wait_for_selector("#document-detail .timeline li")
    detail = page.inner_text("#document-detail")
    assert "Cadena de custodia" in detail and "Solicitud creada por el sistema integrador" in detail
    assert "Nueva versión registrada: v2, vigente" in detail
    assert "Detalle técnico" in detail and "ID de transacción" in detail and "Hash original (SHA-256)" in detail
    assert "IP de origen" not in detail  # el sistema no registra la IP
    versions = page.locator("#document-detail .version-row")
    assert versions.count() == 2 and "Vigente" in versions.nth(0).inner_text()  # la más nueva primero, marcada

    with page.expect_download() as download:
        versions.nth(1).get_by_role("button", name="Descargar").click()  # v1 original
    path = tmp_path / "v1.pdf"
    download.value.save_as(path)
    assert path.read_bytes().startswith(b"%PDF-") and b"/ByteRange" not in path.read_bytes()
    assert download.value.suggested_filename.endswith(".pdf") and "-v1" not in download.value.suggested_filename

    page.get_by_role("button", name="← Volver a Documentos").click()
    page.wait_for_selector("#requests-table table")
    assert page.is_hidden("#document-detail")


def test_la_descarga_con_token_invalido_cierra_la_sesion(live, page):
    sign_local(live, "Persona")
    open_documents(page, live)
    page.locator("#requests-table button", has_text="Ver detalle").first.click()
    page.wait_for_selector("#document-detail .timeline li")
    live.settings.admin_token = "otro-token-" + "z" * 30  # el servidor cambió su token
    page.locator("#document-detail .version-row").first.get_by_role("button", name="Descargar").click()
    page.wait_for_selector("#login-error:not([hidden])")


# --- Integradores -------------------------------------------------------------------------------------


def open_integrators(page, live):
    live.settings.admin_token = TOKEN
    login(page, live, TOKEN)
    page.click(".sidebar button[data-tab=integrators]")
    page.wait_for_selector("#integrators-table table")


def create_integrator(page, name="Gestor e2e", origins="https://gestor.example.org"):
    page.fill("#integrator-form input[name=name]", name)
    page.fill("#integrator-form textarea[name=origins]", origins)
    page.click("#integrator-form button[type=submit]")
    page.wait_for_selector("#credentials:not([hidden])")


def test_alta_de_un_integrador_muestra_las_credenciales_una_sola_vez(live, page):
    open_integrators(page, live)
    create_integrator(page)
    text = page.inner_text("#credentials")
    assert "fdk_" in text and "whsec_" in text and "no se vuelven a mostrar" in text
    api_key = page.locator("#credentials code").nth(0).inner_text()
    secret = page.locator("#credentials code").nth(1).inner_text()
    # ni el almacenamiento del navegador ni el listado guardan las credenciales
    storage = page.evaluate("JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)])")
    assert api_key not in storage and secret not in storage
    assert "Gestor e2e" in page.inner_text("#integrators-table")
    assert api_key not in page.inner_text("#integrators-table")

    page.get_by_role("button", name="Ya las guardé").click()
    assert page.is_hidden("#credentials") and api_key not in page.content()
    page.click(".sidebar button[data-tab=sign]")
    page.click(".sidebar button[data-tab=integrators]")
    assert api_key not in page.content() and secret not in page.content()
    # la API key creada autentica contra la API de integradores
    body = {"document_base64": base64.b64encode(make_pdf()).decode(), "signer": SIGNER, "provider": "local"}
    assert httpx.post(f"{live.base}/api/v1/signature-requests", json=body, headers={"X-API-Key": api_key}).status_code == 201


def test_rotar_la_api_key_pide_confirmacion(live, page):
    open_integrators(page, live)
    create_integrator(page)
    old_key = page.locator("#credentials code").nth(0).inner_text()
    page.get_by_role("button", name="Ya las guardé").click()
    row = page.locator("#integrators-table tr", has_text="Gestor e2e")

    page.once("dialog", lambda d: d.dismiss())  # se cancela: no rota
    row.get_by_role("button", name="Rotar API key").click()
    page.wait_for_timeout(400)
    assert page.is_hidden("#credentials")

    page.once("dialog", lambda d: d.accept())
    row.get_by_role("button", name="Rotar API key").click()
    page.wait_for_selector("#credentials:not([hidden])")
    new_key = page.locator("#credentials code").nth(0).inner_text()
    assert new_key.startswith("fdk_") and new_key != old_key
    body = {"document_base64": base64.b64encode(make_pdf()).decode(), "signer": SIGNER, "provider": "local"}
    assert httpx.post(f"{live.base}/api/v1/signature-requests", json=body, headers={"X-API-Key": old_key}).status_code == 401
    assert httpx.post(f"{live.base}/api/v1/signature-requests", json=body, headers={"X-API-Key": new_key}).status_code == 201


def test_editar_origenes_deshabilitar_y_habilitar(live, page):
    open_integrators(page, live)
    create_integrator(page)
    api_key = page.locator("#credentials code").nth(0).inner_text()
    page.get_by_role("button", name="Ya las guardé").click()
    row = lambda: page.locator("#integrators-table tr", has_text="Gestor e2e")

    row().get_by_role("button", name="Editar orígenes").click()
    page.fill("#origins-form textarea[name=origins]", "https://nuevo.example.org\nhttps://otro.example.org:8443")
    page.click("#origins-form button[type=submit]")
    row().get_by_text("https://nuevo.example.org, https://otro.example.org:8443").wait_for()

    row().get_by_role("button", name="Editar orígenes").click()
    page.fill("#origins-form textarea[name=origins]", "sin-formato")
    page.click("#origins-form button[type=submit]")
    page.wait_for_selector("#message.bad")  # un origen inválido se informa y no cambia nada

    page.once("dialog", lambda d: d.accept())
    row().get_by_role("button", name="Deshabilitar").click()
    row().get_by_text("Deshabilitado").wait_for()
    body = {"document_base64": base64.b64encode(make_pdf()).decode(), "signer": SIGNER, "provider": "local"}
    assert httpx.post(f"{live.base}/api/v1/signature-requests", json=body, headers={"X-API-Key": api_key}).status_code == 401
    row().get_by_role("button", name="Habilitar").click()
    row().get_by_text("Activo").wait_for()
    assert httpx.post(f"{live.base}/api/v1/signature-requests", json=body, headers={"X-API-Key": api_key}).status_code == 201


def test_el_sistema_interno_figura_sin_acciones(live, page):
    # el sistema interno se crea con la primera carga desde el panel
    live.settings.admin_token = TOKEN
    r = httpx.post(
        f"{live.base}/api/v1/admin/signing-uploads",
        json={"filename": "a.pdf", "document_base64": base64.b64encode(make_pdf()).decode()},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert r.status_code == 201, r.text
    open_integrators(page, live)
    row = page.locator("#integrators-table tr", has_text="(interno)")
    assert row.count() == 1 and row.get_by_role("button").count() == 0
