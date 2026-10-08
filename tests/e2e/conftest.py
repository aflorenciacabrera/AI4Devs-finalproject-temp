"""Infraestructura de la prueba de punta a punta: servidor y agente reales, una página anfitriona en
otro origen y un Chrome real (Playwright, con el Chrome del sistema: no se descarga ningún navegador).
"""

import functools
import http.server
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest
import uvicorn
from sqlalchemy import select

from firmadoc.api.deps import settings_dep
from firmadoc.main import app
from firmadoc.models import IntegratingSystem
from firmadoc.seed import DEMO_API_KEY, seed_demo
from firmadoc_agent.server import create_server
from firmadoc_agent.service import AgentService
from firmadoc_agent.testing import FakeUI, SoftwareBackend, SoftwareToken

from ..agent_simulator import AgentSimulator  # noqa: F401 (reexportado para los tests)
from ..pdfs import make_pdf
from ..test_flow import SIGNER

ROOT = Path(__file__).resolve().parents[2]
WIDGET_DIST = ROOT / "widget" / "dist"
EXAMPLES = ROOT / "widget" / "examples"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def browser():
    # Alcance de módulo (no de sesión): la API síncrona de Playwright mantiene un event loop en el
    # hilo principal mientras está activa, y eso rompe las pruebas que usan `asyncio.run` (pyHanko).
    sync_api = pytest.importorskip("playwright.sync_api")
    if not (WIDGET_DIST / "index.html").exists():
        pytest.skip("el widget no está compilado: ejecutar `npm run build` en widget/")
    with sync_api.sync_playwright() as p:
        try:
            instance = p.chromium.launch(channel="chrome", headless=True)
        except Exception as e:  # noqa: BLE001 - cualquier fallo al lanzar = Chrome no disponible
            pytest.skip(f"Chrome no disponible para Playwright: {e}")
        yield instance
        instance.close()


@dataclass
class LiveAgent:
    server: object
    backend: SoftwareBackend
    ui: FakeUI
    port: int

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@dataclass
class Live:
    base: str  # origen del servidor (y del widget)
    host_origin: str  # origen de la página anfitriona (otro origen)
    host_port: int
    agent_port: int
    settings: object
    session: object
    agents: list

    def create_request(self, provider="token", **extra) -> dict:
        body = {
            "document_base64": __import__("base64").b64encode(make_pdf()).decode(),
            "external_document_id": "exp-e2e/doc-1",
            "signer": SIGNER,
            "provider": provider,
            **extra,
        }
        r = httpx.post(f"{self.base}/api/v1/signature-requests", json=body, headers={"X-API-Key": DEMO_API_KEY})
        assert r.status_code == 201, r.text
        return r.json()

    def get_request(self, request_id: str) -> dict:
        r = httpx.get(f"{self.base}/api/v1/signature-requests/{request_id}", headers={"X-API-Key": DEMO_API_KEY})
        return r.json()

    def host_url(self, signing_url: str, mode="iframe", origin: str | None = None) -> str:
        return f"{origin or self.host_origin}/host.html#signing_url={quote(signing_url, safe='')}&mode={mode}"

    def start_agent(self, identity, pin="1234", user_pin: str | None = "1234", port: int | None = None) -> LiveAgent:
        token = SoftwareToken("SERIE1:01", identity.der, identity.key)
        backend = SoftwareBackend([token], pin=pin)
        ui = FakeUI(pin=user_pin)
        port = port or self.agent_port
        server = create_server(AgentService(backend, ui), [self.base], port=port)
        threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True).start()
        agent = LiveAgent(server, backend, ui, port)
        self.agents.append(agent)
        return agent


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture
def live(settings, session, token_env, pki):
    seed_demo(session)
    server_port, host_port, agent_port = free_port(), free_port(), free_port()
    base = f"http://127.0.0.1:{server_port}"
    host_origin = f"http://localhost:{host_port}"

    token_env.public_base_url = base
    token_env.widget_dist = str(WIDGET_DIST)
    token_env.signing_secret = "e2e-secreto-de-pruebas-" + "x" * 20
    token_env.agent_url = f"http://127.0.0.1:{agent_port}"
    system = session.scalars(select(IntegratingSystem)).first()
    system.allowed_origins = host_origin  # el integrador solo permite a su propia página
    session.commit()

    app.dependency_overrides[settings_dep] = lambda: token_env
    uvicorn_server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=server_port, log_level="warning"))
    threading.Thread(target=uvicorn_server.run, daemon=True).start()

    handler = functools.partial(_QuietHandler, directory=str(EXAMPLES))
    host_server = http.server.ThreadingHTTPServer(("127.0.0.1", host_port), handler)
    threading.Thread(target=host_server.serve_forever, daemon=True).start()

    deadline = time.time() + 15
    while not uvicorn_server.started:
        assert time.time() < deadline, "el servidor no arrancó"
        time.sleep(0.05)

    live_env = Live(base, host_origin, host_port, agent_port, token_env, session, [])
    yield live_env

    for agent in live_env.agents:
        agent.stop()
    host_server.shutdown()
    host_server.server_close()
    uvicorn_server.should_exit = True
    app.dependency_overrides.clear()


@pytest.fixture
def page(browser):
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    page.set_default_timeout(20_000)
    page.console_messages = []  # type: ignore[attr-defined]
    page.on("console", lambda m: page.console_messages.append(m.text))  # type: ignore[attr-defined]
    yield page
    context.close()
