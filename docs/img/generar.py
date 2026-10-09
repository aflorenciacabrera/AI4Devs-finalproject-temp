"""Genera las capturas del README (docs/img/*.png) con el modo demo y un Chrome real.

Uso (desde la raíz del repositorio, con el entorno virtual activo y el widget compilado):

    python docs/img/generar.py

Levanta el servidor en modo demostración sobre una carpeta temporal (no toca data/demo), recorre las pantallas con
datos ficticios y guarda los PNG junto a este script. No forma parte de la suite de pruebas.
"""

import re
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend" / "src"))

from firmadoc import demo  # noqa: E402
from firmadoc.main import app  # noqa: E402
from firmadoc.seed import demo_pdf  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def files(names):
    return [{"name": n, "mimeType": "application/pdf", "buffer": demo_pdf(n.removesuffix(".pdf"))} for n in names]


def main() -> int:
    if not (ROOT / "widget" / "dist" / "index.html").is_file():
        print("Falta compilar el widget: cd widget && npm run build", file=sys.stderr)
        return 1
    port = free_port()
    workdir = Path(tempfile.mkdtemp(prefix="firmadoc-capturas-"))
    env = demo.prepare(workdir / "demo", port)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_context(viewport={"width": 1280, "height": 860}, locale="es-AR").new_page()
        page.set_default_timeout(20_000)

        page.goto(env.admin_url)
        page.fill("#token", env.admin_token)
        page.click("#login-form button[type=submit]")
        page.wait_for_selector("#tab-sign:not([hidden])")
        page.screenshot(path=OUT / "01-firmar-documento.png")

        # firma individual con «Firma propia»
        page.set_input_files("#sign-file", files(["Resolucion_0142-2026.pdf"]))
        widget = page.frame_locator("#sign-widget iframe")
        widget.get_by_role("heading", name="Elegí el método de firma", level=1).wait_for()
        page.wait_for_timeout(1500)
        page.locator("#sign-widget iframe").screenshot(path=OUT / "02-widget-metodo.png")
        widget.get_by_role("radio", name=re.compile("Firma propia")).check()
        widget.get_by_role("button", name="Firmar documento").click()
        widget.get_by_role("heading", name="Firmar el documento", level=1).wait_for()
        widget.get_by_role("button", name="Firmar", exact=True).click()
        widget.get_by_role("heading", name="Documento firmado correctamente", level=1).wait_for()
        page.locator("#sign-widget iframe").screenshot(path=OUT / "03-widget-firmado.png")

        # lote de tres documentos
        page.click("#sign-remove")
        page.set_input_files("#sign-file", files(["Providencia_0098-2026.pdf", "Oficio_0231-2026.pdf", "Dictamen_0177-2026.pdf"]))
        page.click("#sign-staged-go")
        widget = page.frame_locator("#sign-widget iframe")
        widget.get_by_role("heading", name="Elegí el método de firma", level=1).wait_for()
        page.wait_for_timeout(1500)
        page.locator("#sign-widget iframe").screenshot(path=OUT / "04-widget-lote.png")
        widget.get_by_role("radio", name=re.compile("Firma propia")).check()
        widget.get_by_role("button", name="Firmar 3 documentos").click()
        widget.get_by_role("heading", name="Firmar el documento", level=1).wait_for()
        widget.get_by_role("button", name="Firmar", exact=True).click()
        widget.get_by_role("heading", name="Firma en lote completada", level=1).wait_for()
        page.locator("#sign-widget iframe").screenshot(path=OUT / "05-widget-resultado-lote.png")

        # panel: documentos, detalle e integradores
        page.click(".sidebar button[data-tab=documents]")
        page.wait_for_selector("#requests-table table tr:nth-child(3)")
        page.screenshot(path=OUT / "06-documentos.png")
        page.locator("#requests-table tr", has_text="Resolucion_0142-2026").get_by_role("button", name="Ver detalle").click()
        page.wait_for_selector("#document-detail .timeline li")
        page.screenshot(path=OUT / "07-detalle-custodia.png", full_page=True)
        page.click(".sidebar button[data-tab=integrators]")
        page.wait_for_selector("#integrators-table table")
        page.screenshot(path=OUT / "08-integradores.png")
        browser.close()

    server.should_exit = True
    print("Capturas guardadas en docs/img/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
