from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import webhooks
from .api import deps
from .api.pages import router as pages_router
from .api.routes import router
from .api.widget_routes import router as widget_router
from .errors import DomainError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranca el trabajador de webhooks (si está habilitado) y lo detiene al apagar."""
    settings = app.dependency_overrides.get(deps.settings_dep, deps.settings_dep)()
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
