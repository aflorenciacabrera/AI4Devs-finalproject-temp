"""Panel Angular (`frontend/`): sirve el build compilado con la CSP del panel y un nonce por pedido.

Angular y PrimeNG inyectan sus estilos en tiempo de ejecución; la CSP los admite solo con el nonce que
el servidor escribe en el atributo `ngCspNonce` del `index.html` (marcador `FIRMADOC_NONCE`).
"""

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from ..config import Settings
from ..errors import NotFound
from .deps import settings_dep

router = APIRouter()

NONCE_PLACEHOLDER = "FIRMADOC_NONCE"
NOT_BUILT = {
    "detail": "El panel no está compilado: ejecute `npm run build` en frontend/.",
    "code": "frontend_not_built",
}


def _dist(settings: Settings) -> Path:
    return Path(settings.frontend_dist).resolve()


def page_headers(nonce: str) -> dict[str, str]:
    csp = "; ".join(
        [
            "default-src 'none'",
            "script-src 'self'",
            f"style-src 'self' 'nonce-{nonce}'",
            "font-src 'self'",
            "connect-src 'self'",
            "img-src 'self' data:",
            "frame-src 'self'",
            "base-uri 'self'",  # el build de Angular lleva <base href="/panel/">; solo el propio origen
            "form-action 'none'",
            "frame-ancestors 'none'",
        ]
    )
    return {
        "Content-Security-Policy": csp,
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }


def _check_enabled(settings: Settings) -> None:
    if not settings.admin_token:
        raise NotFound("no encontrado")


def _index(settings: Settings):
    index = _dist(settings) / "index.html"
    if not index.is_file():
        return JSONResponse(NOT_BUILT, status_code=503)
    nonce = secrets.token_urlsafe(16)
    html = index.read_text(encoding="utf-8").replace(NONCE_PLACEHOLDER, nonce)
    return HTMLResponse(html, headers=page_headers(nonce))


@router.get("/panel", include_in_schema=False)
def panel_page(settings: Settings = Depends(settings_dep)):
    _check_enabled(settings)
    return _index(settings)


@router.get("/panel/{path:path}", include_in_schema=False)
def panel_asset(path: str, settings: Settings = Depends(settings_dep)):
    _check_enabled(settings)
    if not path:
        return _index(settings)
    dist = _dist(settings)
    target = (dist / path).resolve()
    if dist not in target.parents or not target.is_file():
        raise NotFound("no encontrado")
    return FileResponse(target, headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"})
