"""Administración de sistemas integradores desde el panel: alta, orígenes, claves y habilitación.

Cada acción queda en `admin_event` (append-only) sin secretos. La API key y el secreto de webhook en claro
solo salen en la respuesta de crear y de rotar; de la API key solo se guarda el hash.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import Conflict, NotFound, Unprocessable
from ..integrators import (
    RESERVED_NAMES,
    hash_api_key,
    new_api_key,
    new_webhook_secret,
    parse_origins,
)
from ..models import IntegratingSystem
from . import admin


def _is_internal(system: IntegratingSystem) -> bool:
    return system.name in RESERVED_NAMES


def _view(system: IntegratingSystem) -> dict:
    """Lo que se muestra de un integrador: nunca el hash de la clave ni el secreto."""
    return {
        "id": system.id,
        "name": system.name,
        "allowed_origins": [o for o in (system.allowed_origins or "").split(",") if o],
        "has_webhook_secret": bool(system.webhook_secret),
        "status": "disabled" if system.disabled_at is not None else "active",
        "internal": _is_internal(system),
        "created_at": system.created_at,
    }


def _get(db: Session, system_id: uuid.UUID, *, modifiable: bool = True) -> IntegratingSystem:
    system = db.get(IntegratingSystem, system_id)
    if system is None:
        raise NotFound("integrador inexistente")
    if modifiable and _is_internal(system):
        raise Conflict("el sistema interno del panel no se puede modificar")
    return system


def _origins(raw: list[str]) -> str:
    try:
        return parse_origins(",".join(raw))
    except ValueError as e:
        raise Unprocessable(str(e)) from e


def list_integrators(db: Session) -> list[dict]:
    systems = db.scalars(select(IntegratingSystem).order_by(IntegratingSystem.name)).all()
    return [_view(s) for s in systems]


def create(db: Session, name: str, origins: list[str]) -> dict:
    name = name.strip()
    if not name:
        raise Unprocessable("el nombre es obligatorio")
    if name in RESERVED_NAMES:
        raise Unprocessable(f"el nombre {name!r} está reservado para uso interno")
    if db.scalar(select(IntegratingSystem).where(IntegratingSystem.name == name)) is not None:
        raise Unprocessable(f"ya existe un sistema llamado {name!r}")
    allowed = _origins(origins)
    api_key, secret = new_api_key(), new_webhook_secret()
    system = IntegratingSystem(
        name=name, api_key_hash=hash_api_key(api_key), allowed_origins=allowed, webhook_secret=secret
    )
    db.add(system)
    db.flush()
    admin.record(db, "integrator_created", {"integrator_id": str(system.id), "name": name, "origins": allowed})
    db.commit()
    return {**_view(system), "api_key": api_key, "webhook_secret": secret}


def update_origins(db: Session, system_id: uuid.UUID, origins: list[str]) -> dict:
    system = _get(db, system_id)
    before, after = system.allowed_origins, _origins(origins)
    system.allowed_origins = after
    admin.record(
        db,
        "integrator_origins_changed",
        {"integrator_id": str(system.id), "name": system.name, "from": before, "to": after},
    )
    db.commit()
    return _view(system)


def rotate_webhook_secret(db: Session, system_id: uuid.UUID) -> dict:
    system = _get(db, system_id)
    secret = new_webhook_secret()
    system.webhook_secret = secret
    admin.record(db, "integrator_webhook_secret_rotated", {"integrator_id": str(system.id), "name": system.name})
    db.commit()
    return {**_view(system), "webhook_secret": secret}


def rotate_api_key(db: Session, system_id: uuid.UUID) -> dict:
    system = _get(db, system_id)
    api_key = new_api_key()
    system.api_key_hash = hash_api_key(api_key)
    admin.record(db, "integrator_api_key_rotated", {"integrator_id": str(system.id), "name": system.name})
    db.commit()
    return {**_view(system), "api_key": api_key}


def set_enabled(db: Session, system_id: uuid.UUID, enabled: bool) -> dict:
    system = _get(db, system_id)
    system.disabled_at = None if enabled else datetime.now(UTC)
    admin.record(
        db,
        "integrator_enabled" if enabled else "integrator_disabled",
        {"integrator_id": str(system.id), "name": system.name},
    )
    db.commit()
    return _view(system)
