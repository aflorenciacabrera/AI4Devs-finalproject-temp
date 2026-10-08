import hashlib
import hmac
from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import make_engine, make_session_factory
from ..errors import NotFound, Unauthorized
from ..models import IntegratingSystem
from ..services.signature_flow import Ctx
from ..storage import DocumentStorage, LocalFileStorage


@lru_cache
def _session_factory(url: str):
    return make_session_factory(make_engine(url))


@lru_cache
def _settings() -> Settings:
    return get_settings()


def settings_dep() -> Settings:
    return _settings()


def get_db(settings: Settings = Depends(settings_dep)) -> Iterator[Session]:
    with _session_factory(settings.database_url)() as session:
        yield session


def get_storage(settings: Settings = Depends(settings_dep)) -> DocumentStorage:
    return LocalFileStorage(settings.storage_dir)


def current_system(
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> IntegratingSystem:
    if not x_api_key:
        raise Unauthorized("falta la cabecera X-API-Key")
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    system = db.scalar(select(IntegratingSystem).where(IntegratingSystem.api_key_hash == key_hash))
    if system is None:
        raise Unauthorized("API key inválida")
    return system


def get_ctx(
    db: Session = Depends(get_db),
    storage: DocumentStorage = Depends(get_storage),
    settings: Settings = Depends(settings_dep),
    system: IntegratingSystem = Depends(current_system),
) -> Ctx:
    return Ctx(db=db, storage=storage, settings=settings, system=system)


def session_ref(x_session_ref: str | None = Header(default=None)) -> str | None:
    return x_session_ref


def admin_auth(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(settings_dep),
) -> str:
    """Token de administración (distinto de las API keys). Sin token configurado: no existe (404)."""
    if not settings.admin_token:
        raise NotFound("no encontrado")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(
        token.strip().encode(), settings.admin_token.encode()
    ):
        raise Unauthorized("credenciales de administración inválidas")
    return "admin"
