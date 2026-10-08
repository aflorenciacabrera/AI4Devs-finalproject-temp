from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import mock_firmar, preflight, webhooks
from .api import deps
from .api.admin_pages import router as admin_pages_router
from .api.admin_routes import router as admin_router
from .api.firmar_routes import router as firmar_router
from .api.pages import router as pages_router
from .api.routes import router
from .api.widget_batch_routes import router as widget_batch_router
from .api.widget_routes import router as widget_router
from .errors import DomainError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranca el trabajador de webhooks (si está habilitado) y lo detiene al apagar."""
    settings = app.dependency_overrides.get(deps.settings_dep, deps.settings_dep)()
    if settings.real_mode:  # no se sirve nada con una configuración insegura
        bad = preflight.errors(preflight.check(settings))
        if bad:
            detail = "\n".join(f"  - {f.code}: {f.message}" for f in bad)
            raise RuntimeError(f"configuración inválida para el modo real:\n{detail}")
    worker = None
    if settings.webhook_worker_enabled:
        worker = webhooks.WebhookWorker(settings, deps._session_factory(settings.database_url)).start()
    try:
        yield
    finally:
        if worker is not None:
            worker.stop()


app = FastAPI(title="Firmadoc", lifespan=lifespan)
app.include_router(router)
app.include_router(widget_router)
app.include_router(widget_batch_router)
app.include_router(admin_router)
app.include_router(firmar_router)
app.include_router(mock_firmar.router)
app.include_router(admin_pages_router)
app.include_router(pages_router)


@app.exception_handler(DomainError)
def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    content = {"detail": exc.detail}
    if exc.code:
        content["code"] = exc.code
    return JSONResponse(status_code=exc.status_code, content=content)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
