import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from firmadoc.main import app
from firmadoc.models import IntegratingSystem

from .test_flow import create


@pytest.fixture
def dist(settings, tmp_path):
    """Un widget "compilado" de mentira, más un archivo secreto fuera del directorio."""
    root = tmp_path / "widget-dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>Firmadoc</title>")
    (root / "widget.js").write_text("customElements.define('firmadoc-widget', class extends HTMLElement {});")
    (root / "assets" / "app-abc123.js").write_text("console.log('widget')")
    (root / "assets" / "app-abc123.css").write_text("body{margin:0}")
    (tmp_path / "secreto.txt").write_text("no debe salir")
    settings.widget_dist = str(root)
    return root


@pytest.fixture
def anon(client):
    return TestClient(app)


def request_id(client):
    return create(client).json()["id"]


def csp(response) -> dict[str, str]:
    directives = {}
    for part in response.headers["content-security-policy"].split(";"):
        name, _, value = part.strip().partition(" ")
        directives[name] = value
    return directives


# --- /sign/{id} -----------------------------------------------------------------------------


def test_pagina_con_el_origen_permitido(client, anon, dist):
    r = anon.get(f"/sign/{request_id(client)}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "Firmadoc" in r.text
    assert csp(r)["frame-ancestors"] == "http://localhost:4200"


def test_no_hace_falta_token_para_cargar_la_pagina(client, anon, dist):
    """El token viaja en el fragmento: el servidor nunca lo ve, así que no puede exigirlo."""
    assert anon.get(f"/sign/{request_id(client)}").status_code == 200


def test_varios_origenes(client, anon, dist, session):
    system = session.scalars(select(IntegratingSystem)).first()
    system.allowed_origins = "https://a.example.org, https://b.example.org"
    session.commit()
    r = anon.get(f"/sign/{request_id(client)}")
    assert csp(r)["frame-ancestors"] == "https://a.example.org https://b.example.org"


def test_integrador_sin_origenes_no_puede_ser_enmarcado(client, anon, dist, session):
    system = session.scalars(select(IntegratingSystem)).first()
    system.allowed_origins = ""
    session.commit()
    assert csp(anon.get(f"/sign/{request_id(client)}"))["frame-ancestors"] == "'none'"


def test_cabeceras_de_seguridad_de_la_pagina(client, anon, dist):
    r = anon.get(f"/sign/{request_id(client)}")
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    policy = csp(r)
    assert policy["default-src"] == "'none'"
    assert policy["script-src"] == "'self'"  # sin 'unsafe-inline' ni 'unsafe-eval'
    assert "unsafe" not in r.headers["content-security-policy"]
    assert policy["connect-src"] == "'self' http://127.0.0.1:47123"  # solo el servidor y el agente
    assert policy["base-uri"] == "'none'" and policy["form-action"] == "'none'"


def test_el_origen_del_agente_sale_de_la_configuracion(client, anon, dist, settings):
    settings.agent_url = "http://127.0.0.1:50000/ruta"
    r = anon.get(f"/sign/{request_id(client)}")
    assert csp(r)["connect-src"] == "'self' http://127.0.0.1:50000"


def test_solicitud_inexistente_sin_pistas(anon, dist):
    r = anon.get(f"/sign/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.content == b"" and "content-security-policy" not in r.headers


def test_identificador_mal_formado(anon, dist):
    assert anon.get("/sign/no-es-un-uuid").status_code == 422


def test_widget_sin_compilar(client, anon, settings, tmp_path):
    settings.widget_dist = str(tmp_path / "no-existe")
    r = anon.get(f"/sign/{request_id(client)}")
    assert r.status_code == 503 and r.json()["code"] == "widget_not_built"
    assert anon.get("/widget.js").status_code == 503
    # la API de integración sigue funcionando sin el widget
    assert create(client).status_code == 201


# --- recursos estáticos ---------------------------------------------------------------------


def test_assets_con_tipo_de_contenido_y_cache(anon, dist):
    js = anon.get("/widget-assets/assets/app-abc123.js")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    assert "immutable" in js.headers["cache-control"]
    css = anon.get("/widget-assets/assets/app-abc123.css")
    assert css.status_code == 200 and css.headers["content-type"].startswith("text/css")


def test_widget_js(anon, dist):
    r = anon.get("/widget.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    assert r.headers["cross-origin-resource-policy"] == "cross-origin"  # lo cargan otros sitios
    assert r.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize(
    "path",
    [
        "/widget-assets/%2e%2e/secreto.txt",
        "/widget-assets/..%2fsecreto.txt",
        "/widget-assets/assets/%2e%2e/%2e%2e/secreto.txt",
        "/widget-assets/no-existe.js",
        "/widget-assets/assets",
    ],
)
def test_no_se_sale_del_directorio(anon, dist, path):
    r = anon.get(path)
    assert r.status_code == 404
    assert "no debe salir" not in r.text
