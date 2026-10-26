"""Página de administración: estáticos propios, sin dependencias ni scripts en línea."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from ..config import Settings
from ..errors import NotFound
from .deps import settings_dep

router = APIRouter()

UI_DIR = Path(__file__).resolve().parent.parent / "admin_ui"
FILES = {
    "": ("index.html", "text/html; charset=utf-8"),
    "admin.js": ("admin.js", "text/javascript; charset=utf-8"),
    "admin.css": ("admin.css", "text/css; charset=utf-8"),
}
HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "img-src 'self' data:; frame-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def _serve(name: str, settings: Settings) -> FileResponse:
    if not settings.admin_token:
        raise NotFound("no encontrado")
    file_name, media_type = FILES[name]
    return FileResponse(UI_DIR / file_name, media_type=media_type, headers=HEADERS)


@router.get("/admin", include_in_schema=False)
def admin_page(settings: Settings = Depends(settings_dep)):
    return _serve("", settings)


@router.get("/admin/{asset}", include_in_schema=False)
def admin_asset(asset: str, settings: Settings = Depends(settings_dep)):
    if asset not in FILES or not asset:
        raise NotFound("no encontrado")
    return _serve(asset, settings)
