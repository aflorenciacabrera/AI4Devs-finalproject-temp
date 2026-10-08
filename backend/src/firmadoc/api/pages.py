"""Entrega del widget compilado: la página de firma y sus recursos estáticos."""

import uuid
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import IntegratingSystem, SignatureBatch, SignatureRequest
from ..services.widget import allowed_origins
from .deps import get_db, settings_dep

router = APIRouter()

NOT_BUILT = {
    "detail": "El widget no está compilado: ejecute `npm run build` en widget/.",
    "code": "widget_not_built",
}


def _dist(settings: Settings) -> Path:
    return Path(settings.widget_dist).resolve()


def _agent_origin(settings: Settings) -> str:
    parts = urlsplit(settings.agent_url)
    return f"{parts.scheme}://{parts.netloc}"


def page_headers(settings: Settings, origins: list[str]) -> dict[str, str]:
    """Cabeceras de la página del widget. `frame-ancestors` es la defensa contra clickjacking."""
    ancestors = " ".join(origins) if origins else "'none'"
    csp = "; ".join(
        [
            "default-src 'none'",
            "script-src 'self'",
            "style-src 'self'",
            "font-src 'self'",
            "img-src 'self' data:",
            f"connect-src 'self' {_agent_origin(settings)}",
            "base-uri 'none'",
            "form-action 'none'",
            f"frame-ancestors {ancestors}",
        ]
    )
    return {
        "Content-Security-Policy": csp,
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }


@router.get("/sign/{request_id}")
def sign_page(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    request = db.get(SignatureRequest, request_id)
    if request is None:
        return Response(status_code=404)  # sin cabeceras de widget ni detalle
    index = _dist(settings) / "index.html"
    if not index.is_file():
        return JSONResponse(NOT_BUILT, status_code=503)
    system = db.get(IntegratingSystem, request.integrating_system_id)
    return FileResponse(
        index, media_type="text/html; charset=utf-8", headers=page_headers(settings, allowed_origins(system))
    )


@router.get("/sign/batch/{batch_id}")
def sign_batch_page(
    batch_id: uuid.UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    batch = db.get(SignatureBatch, batch_id)
    if batch is None:
        return Response(status_code=404)  # sin cabeceras de widget ni detalle
    index = _dist(settings) / "index.html"
    if not index.is_file():
        return JSONResponse(NOT_BUILT, status_code=503)
    system = db.get(IntegratingSystem, batch.integrating_system_id)
    return FileResponse(
        index, media_type="text/html; charset=utf-8", headers=page_headers(settings, allowed_origins(system))
    )


@router.get("/widget-assets/{path:path}")
def widget_asset(path: str, settings: Settings = Depends(settings_dep)):
    dist = _dist(settings)
    target = (dist / path).resolve()
    if dist not in target.parents or not target.is_file():
        return Response(status_code=404)
    return FileResponse(
        target,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/widget.js")
def widget_script(settings: Settings = Depends(settings_dep)):
    script = _dist(settings) / "widget.js"
    if not script.is_file():
        return JSONResponse(NOT_BUILT, status_code=503)
    return FileResponse(
        script,
        media_type="text/javascript; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Cross-Origin-Resource-Policy": "cross-origin",
            "X-Content-Type-Options": "nosniff",
        },
    )
