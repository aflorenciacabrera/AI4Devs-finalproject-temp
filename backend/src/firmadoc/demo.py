"""Modo demostración: prepara y arranca Firmadoc para probarlo sin token USB.

Uso: `python -m firmadoc.demo [--port 8000] [--host 127.0.0.1] [--reset]`

Crea (o reutiliza) un entorno aislado en `data/demo/` con su base SQLite, sus documentos y su certificado de
demostración, aplica las migraciones, carga el seed y arranca el servidor. El método de firma sin token es
«Firma propia» (proveedor `local`). No es el modo real: ver `docs/real-mode.md`.
"""

import argparse
import json
import os
import secrets
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from . import demo_pki

ROOT = Path(__file__).resolve().parents[3]  # raíz del repositorio (backend/src/firmadoc/demo.py)
DEMO_DIR_NAME = "demo"
SECRETS_FILE = "demo.json"


class DemoError(Exception):
    """El entorno de demostración no se puede preparar (mensaje listo para mostrar)."""


@dataclass(frozen=True)
class DemoEnv:
    directory: Path
    port: int
    admin_token: str
    signing_secret: str
    public_base_url: str
    database_url: str
    created: bool  # True si el seed se cargó en esta ejecución
    widget_built: bool
    frontend_built: bool = False  # panel Angular compilado (frontend/dist)
    token_dir: Path | None = None  # PKI de prueba para firmar con el agente (token de software)

    @property
    def admin_url(self) -> str:
        return f"{self.public_base_url}/admin"

    @property
    def agent_command(self) -> str:
        """Cómo arrancar Firmadoc Agent con el token de prueba (ruta relativa a la raíz si se puede)."""
        pem = (self.token_dir or self.directory / "token") / demo_pki.SIGNER_FILE
        try:
            shown = pem.relative_to(Path.cwd()).as_posix()
        except ValueError:
            shown = str(pem)
        return f"firmadoc-agent run --software-token {shown} --origin {self.public_base_url}"

    @property
    def panel_url(self) -> str:
        return f"{self.public_base_url}/panel"


def default_directory() -> Path:
    return Path.cwd() / "data" / DEMO_DIR_NAME


def _load_or_create_secrets(directory: Path) -> dict[str, str]:
    path = directory / SECRETS_FILE
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf8"))
        if len(data.get("admin_token", "")) >= 32 and len(data.get("signing_secret", "")) >= 32:
            return data
    data = {"admin_token": secrets.token_urlsafe(32), "signing_secret": secrets.token_urlsafe(32)}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf8")
    return data


def reset(directory: Path) -> None:
    """Borra el entorno de demostración. Solo una carpeta llamada exactamente `demo`."""
    if directory.name != DEMO_DIR_NAME:
        raise DemoError(f"por seguridad, --reset solo borra una carpeta llamada «{DEMO_DIR_NAME}»: {directory}")
    if directory.exists():
        shutil.rmtree(directory)


def widget_dist() -> Path:
    return ROOT / "widget" / "dist"


def frontend_dist() -> Path:
    return ROOT / "frontend" / "dist" / "firmadoc-panel" / "browser"


def check_not_real_mode() -> None:
    if os.environ.get("FIRMADOC_REAL_MODE", "").strip().lower() in ("1", "true", "yes", "on"):
        raise DemoError(
            "FIRMADOC_REAL_MODE está activo: el modo demostración no se usa con el modo real. "
            "Desactivalo (FIRMADOC_REAL_MODE=false) para probar sin token."
        )


def prepare(directory: Path, port: int = 8000) -> DemoEnv:
    """Deja el entorno listo (carpetas, secretos, variables, migraciones y seed). No arranca el servidor."""
    check_not_real_mode()
    if not (ROOT / "alembic.ini").is_file():
        raise DemoError(f"no se encontró el proyecto en {ROOT}: ejecutá el comando desde una copia del repositorio")

    from alembic import command
    from alembic.config import Config

    from .db import make_engine, make_session_factory
    from .seed import seed_demo
    from .storage import LocalFileStorage

    directory.mkdir(parents=True, exist_ok=True)
    (directory / "storage").mkdir(exist_ok=True)
    (directory / "local-cert").mkdir(exist_ok=True)
    keys = _load_or_create_secrets(directory)

    database_url = f"sqlite:///{(directory / 'firmadoc-demo.db').as_posix()}"
    public_base_url = f"http://localhost:{port}"
    # Token de prueba: AC y certificado con CUIL para firmar con el agente en modo token de software.
    pki = demo_pki.ensure_demo_pki(directory / "token")
    trust_dir = demo_pki.ensure_trust_dir(directory / "trust", ROOT / "backend" / "trust", pki)
    os.environ.update(
        {
            "FIRMADOC_DATABASE_URL": database_url,
            "FIRMADOC_STORAGE_DIR": str(directory / "storage"),
            "FIRMADOC_STORAGE_BACKEND": "files",
            "FIRMADOC_LOCAL_CERT_DIR": str(directory / "local-cert"),
            "FIRMADOC_PUBLIC_BASE_URL": public_base_url,
            "FIRMADOC_ADMIN_TOKEN": keys["admin_token"],
            "FIRMADOC_SIGNING_SECRET": keys["signing_secret"],
            "FIRMADOC_WIDGET_DIST": str(widget_dist()),
            "FIRMADOC_FRONTEND_DIST": str(frontend_dist()),
            "FIRMADOC_TRUST_DIR": str(trust_dir),
            "FIRMADOC_PANEL_SIGNER_NAME": demo_pki.DEMO_SIGNER_NAME,
            "FIRMADOC_PANEL_SIGNER_IDENTIFIER": demo_pki.DEMO_SIGNER_CUIL,
            "FIRMADOC_PANEL_SIGNER_EMAIL": demo_pki.DEMO_SIGNER_EMAIL,
            "FIRMADOC_REAL_MODE": "false",
        }
    )

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")

    engine = make_engine(database_url)
    try:
        with make_session_factory(engine)() as session:
            created = seed_demo(session, LocalFileStorage(str(directory / "storage")))
    finally:
        engine.dispose()

    return DemoEnv(
        directory=directory,
        port=port,
        admin_token=keys["admin_token"],
        signing_secret=keys["signing_secret"],
        public_base_url=public_base_url,
        database_url=database_url,
        created=created,
        widget_built=(widget_dist() / "index.html").is_file(),
        frontend_built=(frontend_dist() / "index.html").is_file(),
        token_dir=pki.directory,
    )


def guide(env: DemoEnv) -> str:
    from .seed import DEMO_API_KEY

    lines = [
        "",
        "Firmadoc en modo demostración (sin token USB)",
        "=" * 46,
        f"  Panel:           {env.panel_url}" + ("" if env.frontend_built else "  (sin compilar: ver abajo)"),
        f"  Panel estático:  {env.admin_url}",
        f"  Token de acceso: {env.admin_token}",
        f"  API key demo:    {DEMO_API_KEY} (cabecera X-API-Key, para la API de integradores)",
        f"  Datos en:        {env.directory}",
        "",
        "Para firmar sin token: en el panel, «Firmar documento» → cargá un PDF → elegí «Firma propia».",
        "Es firma electrónica de demostración (sin presunción legal); no usa el token USB ni el agente.",
        "Abrí el panel con la dirección de arriba (localhost): el widget solo se embebe desde ese origen.",
        "",
        "Para probar la firma CON token sin hardware (token de software, solo demostración), en otra terminal:",
        f"  {env.agent_command}",
        f"  PIN del token de prueba: {demo_pki.DEMO_PIN}   "
        + f"(titular: {demo_pki.DEMO_SIGNER_NAME}, CUIL {demo_pki.DEMO_SIGNER_CUIL})",
        "Después, en el panel elegí «Firma con token»: el PIN se ingresa en la ventana del agente.",
    ]
    if not env.widget_built:
        lines += [
            "",
            "AVISO: el widget no está compilado, así que no se verá el módulo de firma.",
            "       Compilalo con:  cd widget && npm install && npm run build",
        ]
    if not env.frontend_built:
        lines += [
            "",
            "AVISO: el panel Angular no está compilado (/panel responde 503); mientras tanto usá el panel estático.",
            "       Compilalo con:  cd frontend && npm install && npm run build",
        ]
    lines += ["", "Ctrl+C para detener.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="firmadoc.demo", description="Arranca Firmadoc en modo demostración.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--reset", action="store_true", help="borra data/demo y empieza de cero")
    parser.add_argument("--prepare-only", action="store_true", help="prepara el entorno y no arranca el servidor")
    args = parser.parse_args(argv)

    # La consola de Windows (cp1252) no codifica todo (flechas, emoji en la ruta): se reemplaza en vez de fallar.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    directory = default_directory()
    try:
        check_not_real_mode()  # antes de borrar nada
        if args.reset:
            reset(directory)
        env = prepare(directory, args.port)
    except DemoError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(guide(env))
    if args.prepare_only:
        return 0

    import uvicorn

    uvicorn.run("firmadoc.main:app", host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
