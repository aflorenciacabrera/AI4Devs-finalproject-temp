"""Panel Angular servido en /panel: cabeceras, nonce por pedido, build ausente y recorrido de rutas."""

import re

import pytest

from firmadoc.api.frontend_pages import NONCE_PLACEHOLDER

TOKEN = "t0ken-de-administracion-" + "x" * 20
INDEX = f'<!doctype html><html><body><app-root ngCspNonce="{NONCE_PLACEHOLDER}"></app-root></body></html>'


@pytest.fixture
def admin(client, settings):
    settings.admin_token = TOKEN
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def dist(settings, tmp_path):
    folder = tmp_path / "browser"
    folder.mkdir()
    (folder / "index.html").write_text(INDEX, encoding="utf-8")
    (folder / "main-ABC123.js").write_text("console.log('panel')", encoding="utf-8")
    settings.frontend_dist = str(folder)
    return folder


def nonce_of(response) -> str:
    csp = response.headers["content-security-policy"]
    style = next(p for p in csp.split("; ") if p.startswith("style-src"))
    match = re.fullmatch(r"style-src 'self' 'nonce-([A-Za-z0-9_-]+)'", style)
    assert match, style
    return match.group(1)


def test_pagina_con_csp_y_nonce(client, admin, dist):
    r = client.get("/panel")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    nonce = nonce_of(r)
    assert f'ngCspNonce="{nonce}"' in r.text
    assert NONCE_PLACEHOLDER not in r.text
    csp = r.headers["content-security-policy"]
    for directive in (
        "default-src 'none'",
        "script-src 'self'",
        "connect-src 'self'",
        "frame-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",  # el build lleva <base href="/panel/">
    ):
        assert directive in csp
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_nonce_distinto_por_pedido(client, admin, dist):
    assert nonce_of(client.get("/panel")) != nonce_of(client.get("/panel"))


def test_barra_final_tambien_sirve_la_pagina(client, admin, dist):
    r = client.get("/panel/")
    assert r.status_code == 200 and "ngCspNonce" in r.text


def test_recursos_del_build(client, admin, dist):
    r = client.get("/panel/main-ABC123.js")
    assert r.status_code == 200
    assert "console.log" in r.text
    assert r.headers["x-content-type-options"] == "nosniff"


def test_sin_build_responde_503(client, admin, settings, tmp_path):
    settings.frontend_dist = str(tmp_path / "no-existe")
    r = client.get("/panel")
    assert r.status_code == 503
    assert r.json()["code"] == "frontend_not_built"


def test_deshabilitado_sin_token(client, settings, dist):
    assert settings.admin_token is None
    assert client.get("/panel").status_code == 404
    assert client.get("/panel/main-ABC123.js").status_code == 404


def test_no_sale_del_directorio(client, admin, dist, tmp_path):
    (tmp_path / "secreto.txt").write_text("no", encoding="utf-8")
    assert client.get("/panel/../secreto.txt").status_code == 404
    assert client.get("/panel/%2e%2e/secreto.txt").status_code == 404
    assert client.get("/panel/no-existe.js").status_code == 404
