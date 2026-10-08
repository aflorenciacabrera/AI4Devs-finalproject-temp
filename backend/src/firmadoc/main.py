from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api.routes import router
from .errors import DomainError

app = FastAPI(title="Firmadoc")
app.include_router(router)


@app.exception_handler(DomainError)
def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    content = {"detail": exc.detail}
    if exc.code:
        content["code"] = exc.code
    return JSONResponse(status_code=exc.status_code, content=content)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
