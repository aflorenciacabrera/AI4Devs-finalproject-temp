"""Firma en lote en un Chrome real: un solo PIN, éxito parcial, descarga del ZIP y reintento."""

import base64
import io
import re
import zipfile

import httpx
import pytest

from firmadoc.seed import DEMO_API_KEY

from ..pdfs import make_pdf
from ..test_flow import SIGNER
from ..test_token_flow import signer_identity
from .test_widget_e2e import host_messages, open_widget, wait_for_message

pytestmark = pytest.mark.e2e

BATCH_DONE = "Firma en lote completada"
BATCH_PARTIAL = "Firma en lote finalizada"


def create_batch(live, n=3, provider="token", allowed=("token", "local")):
    body = {
        "documents": [
            {"document_base64": base64.b64encode(make_pdf(f"BT {i} ET".encode())).decode(), "external_document_id": f"lote-e2e/doc-{i}"}
            for i in range(n)
        ],
        "signer": SIGNER,
        "provider": provider,
        "allowed_providers": list(allowed),
    }
    r = httpx.post(f"{live.base}/api/v1/signature-batches", json=body, headers={"X-API-Key": DEMO_API_KEY})
    assert r.status_code == 201, r.text
    return r.json()


def h1(frame, name):
    return frame.get_by_role("heading", name=name, level=1)


def corrupt_second_signature(agent):
    """El agente devuelve una firma inválida para el segundo documento: el servidor la rechaza (422)."""
    original = agent.backend.sign

    def sign(certificate_id, pin, digests):
        signatures = original(certificate_id, pin, digests)
        broken = bytearray(signatures[1])
        broken[0] ^= 0xFF
        signatures[1] = bytes(broken)
        return signatures

    agent.backend.sign = sign


def test_lote_con_token_un_solo_pin(live, page, pki):
    agent = live.start_agent(signer_identity(pki))
    batch = create_batch(live)
    widget = open_widget(page, live, batch)

    h1(widget, "Elegí el método de firma").wait_for()
    assert wait_for_message(page, "firmadoc:ready")["requestId"] == batch["id"]
    assert widget.get_by_role("region", name="Documentos a firmar (3)").get_by_role("listitem").count() == 3
    widget.get_by_text("Firmadoc Agent conectado · token detectado").wait_for()
    assert widget.get_by_role("radio", name=re.compile("Firma con token")).is_checked()
    widget.get_by_role("button", name="Firmar 3 documentos").click()

    h1(widget, "Elegí el certificado").wait_for()
    widget.get_by_role("button", name="Validar y continuar").click()
    h1(widget, BATCH_DONE).wait_for()

    assert len(agent.ui.prompts) == 1  # un solo diálogo de PIN para los 3 documentos
    assert agent.backend.login_attempts == 1  # una sola sesión con el token firmó los 3 hashes
    assert agent.backend.sign_calls == 3
    result = wait_for_message(page, "firmadoc:batch-completed")
    assert (result["signed"], result["total"], result["status"]) == (3, 3, "completed")
    assert all(d["version_number"] == 2 for d in result["documents"])
    assert "token" not in str(result).lower().replace("signed", "") and "base64" not in str(result).lower()
    final = httpx.get(f"{live.base}/api/v1/signature-batches/{batch['id']}", headers={"X-API-Key": DEMO_API_KEY}).json()
    assert final["status"] == "completed"


def test_exito_parcial_zip_y_reintento(live, page, pki, tmp_path):
    agent = live.start_agent(signer_identity(pki))
    corrupt_second_signature(agent)
    batch = create_batch(live)
    widget = open_widget(page, live, batch)

    h1(widget, "Elegí el método de firma").wait_for()
    widget.get_by_role("button", name="Firmar 3 documentos").click()
    h1(widget, "Elegí el certificado").wait_for()
    widget.get_by_role("button", name="Validar y continuar").click()
    h1(widget, BATCH_PARTIAL).wait_for()

    assert widget.get_by_text("2 de 3 documentos firmados").first.is_visible()
    items = widget.get_by_role("listitem")
    assert items.filter(has_text="Firmado · v2").count() == 2
    assert items.filter(has_text="Error:").count() == 1
    result = wait_for_message(page, "firmadoc:batch-completed")
    assert (result["signed"], result["total"], result["status"]) == (2, 3, "partial_failure")

    with page.expect_download() as download:
        widget.get_by_role("button", name="Descargar firmados (2)").click()
    path = tmp_path / "firmados.zip"
    download.value.save_as(path)
    names = zipfile.ZipFile(io.BytesIO(path.read_bytes())).namelist()
    assert len(names) == 2 and all(n.endswith(".pdf") and "-v2" not in n for n in names)

    # reintentar: el widget pasa a otro lote que solo tiene el documento fallido
    agent.backend.sign = type(agent.backend).sign.__get__(agent.backend)  # firma bien esta vez
    widget.get_by_role("button", name="Reintentar (1)").click()
    h1(widget, "Elegí el método de firma").wait_for()
    assert widget.get_by_role("region", name="Documentos a firmar (1)").get_by_role("listitem").count() == 1
    assert widget.get_by_role("button", name="Firmar 1 documentos").is_visible()
    widget.get_by_role("button", name="Firmar 1 documentos").click()
    h1(widget, "Elegí el certificado").wait_for()
    widget.get_by_role("button", name="Validar y continuar").click()
    h1(widget, BATCH_DONE).wait_for()
    assert host_messages(page)  # el anfitrión sigue recibiendo mensajes tras el reintento


def test_la_firma_remota_no_se_ofrece_en_lotes(live, page):
    batch = create_batch(live, n=2, provider="local", allowed=("local",))
    widget = open_widget(page, live, batch)
    h1(widget, "Elegí el método de firma").wait_for()
    remote = widget.get_by_role("radio", name=re.compile("Firma remota"))
    assert remote.is_disabled()
    assert widget.get_by_text("No está disponible para firmar lotes.").is_visible()
