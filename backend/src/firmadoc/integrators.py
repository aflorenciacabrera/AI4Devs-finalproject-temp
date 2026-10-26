"""Alta y mantenimiento de sistemas integradores. Uso: `python -m firmadoc.integrators --help`."""

import argparse
import hashlib
import re
import secrets
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import make_engine, make_session_factory
from .models import IntegratingSystem

ORIGIN = re.compile(r"^https?://[A-Za-z0-9.-]+(:\d{1,5})?$")


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_api_key() -> str:
    return "fdk_" + secrets.token_urlsafe(32)


def new_webhook_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(32)


def parse_origins(raw: str) -> str:
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    for origin in origins:
        if not ORIGIN.match(origin):
            raise ValueError(f"origen inválido: {origin!r} (formato esperado: https://host[:puerto])")
    return ",".join(origins)


RESERVED_NAMES = {"Firmadoc (panel)"}  # sistema interno de la sección «Firmar documento» del panel


def create(db: Session, name: str, origins: str) -> tuple[IntegratingSystem, str, str]:
    """Devuelve el sistema, su API key y su secreto de webhook (solo se muestran esta vez)."""
    if name.strip() in RESERVED_NAMES:
        raise ValueError(f"el nombre {name!r} está reservado para uso interno")
    if db.scalar(select(IntegratingSystem).where(IntegratingSystem.name == name)) is not None:
        raise ValueError(f"ya existe un sistema llamado {name!r}")
    api_key, secret = new_api_key(), new_webhook_secret()
    system = IntegratingSystem(
        name=name, api_key_hash=hash_api_key(api_key), allowed_origins=parse_origins(origins), webhook_secret=secret
    )
    db.add(system)
    db.commit()
    return system, api_key, secret


def rotate_webhook_secret(db: Session, name: str) -> str:
    system = db.scalar(select(IntegratingSystem).where(IntegratingSystem.name == name))
    if system is None:
        raise LookupError(f"no existe el sistema {name!r}")
    system.webhook_secret = new_webhook_secret()
    db.commit()
    return system.webhook_secret


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="firmadoc.integrators")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="crea un sistema integrador")
    c.add_argument("--name", required=True)
    c.add_argument("--origins", default="", help="orígenes permitidos separados por coma")
    r = sub.add_parser("rotate-webhook-secret", help="genera un nuevo secreto de webhook")
    r.add_argument("--name", required=True)
    sub.add_parser("list", help="lista los sistemas (sin secretos)")
    args = parser.parse_args(argv)

    engine = make_engine(get_settings().database_url)
    with make_session_factory(engine)() as db:
        try:
            if args.cmd == "create":
                system, api_key, secret = create(db, args.name, args.origins)
                print(f"Sistema creado: {system.name}\nAPI key (guardarla, no se vuelve a mostrar): {api_key}")
                print(f"Secreto de webhook (idem): {secret}")
            elif args.cmd == "rotate-webhook-secret":
                print(f"Nuevo secreto de webhook (no se vuelve a mostrar): {rotate_webhook_secret(db, args.name)}")
            else:
                for s in db.scalars(select(IntegratingSystem).order_by(IntegratingSystem.name)):
                    print(f"{s.name}\torígenes={s.allowed_origins or '-'}\twebhook={'sí' if s.webhook_secret else 'no'}")
        except (ValueError, LookupError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
