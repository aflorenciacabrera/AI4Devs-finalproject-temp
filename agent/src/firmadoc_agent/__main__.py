"""Punto de entrada: `firmadoc-agent [run|diagnose] [--config RUTA] [--software-token PEM] [--version]`."""

import argparse
import os
import sys
import threading
from dataclasses import replace
from pathlib import Path

from . import __version__
from .config import (
    AgentConfig,
    ConfigError,
    data_dir,
    default_config_path,
    load_config,
    validate_origin,
)
from .diagnose import run_diagnose
from .logs import setup_logging
from .pkcs11_backend import Pkcs11Backend
from .server import create_server
from .service import AgentService


def _attach_parent_console() -> None:
    """El .exe es de ventana (sin consola): si se lo ejecuta desde una terminal, usar la suya."""
    if os.name != "nt" or (sys.stdout is not None and sys.stderr is not None):
        return
    import contextlib
    import ctypes

    with contextlib.suppress(Exception):  # sin consola simplemente no se imprime
        if ctypes.windll.kernel32.AttachConsole(-1):  # ATTACH_PARENT_PROCESS
            console = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)  # noqa: SIM115
            sys.stdout = sys.stderr = console


def _say(message: str) -> None:
    stream = sys.stderr if sys.stderr is not None else None
    if stream is not None:
        print(message, file=stream)


def _load(args) -> AgentConfig | None:
    """Configuración del archivo (si existe) más las opciones de línea de comandos (`--origin`, `--port`)."""
    path = Path(args.config) if args.config else default_config_path()
    try:
        config = load_config(path)
        origins = getattr(args, "origin", None)
        if origins:
            config = replace(config, allowed_origins=tuple(validate_origin(o) for o in origins))
        port = getattr(args, "port", None)
        if port is not None:
            if not 1024 <= port <= 65535:
                raise ConfigError(f"port inválido: {port!r} (debe estar entre 1024 y 65535)")
            config = replace(config, port=port)
        return config
    except ConfigError as e:
        _say(f"Configuración inválida: {e}")
        return None


def _backend(args, config: AgentConfig, log=None):
    """El token: PKCS#11 (normal) o un archivo PEM como token de software (demostración)."""
    if getattr(args, "software_token", None):
        from .software_token import SoftwareTokenError, software_backend

        try:
            backend = software_backend(Path(args.software_token))
        except SoftwareTokenError as e:
            _say(f"Token de software inválido: {e}")
            return None
        if log is not None:
            log.warning("TOKEN DE SOFTWARE (solo demostración): %s", args.software_token)
        return backend
    if log is not None and not config.pkcs11_module:
        log.warning("'pkcs11_module' no está configurado: no se podrá acceder al token")
    return Pkcs11Backend(config.pkcs11_module)


def cmd_run(args, *, ui=None, backend=None) -> int:
    config = _load(args)
    if config is None:
        return 2
    log = setup_logging(config.log_level, data_dir() / "agent.log")
    if not config.allowed_origins:
        log.warning("la lista de orígenes permitidos está vacía: se rechazará todo pedido")

    backend = backend or _backend(args, config, log)
    if backend is None:
        return 2
    service = AgentService(backend, ui)  # la interfaz se asigna después de reservar el puerto
    try:
        server = create_server(service, config.allowed_origins, config.port)
    except OSError as e:
        message = (
            f"No se pudo escuchar en 127.0.0.1:{config.port} ({e}). "
            "Ya hay una instancia del agente o el puerto está en uso."
        )
        log.error(message)
        _say(message)
        return 1

    if ui is None:
        from .ui_tk import TkUI  # tkinter solo hace falta para `run` (no para `diagnose`)

        ui = service.ui = TkUI()

    log.info(
        "agente %s escuchando en 127.0.0.1:%s, orígenes permitidos: %s",
        __version__, server.port, list(config.allowed_origins),
    )
    thread = threading.Thread(target=server.serve_forever, name="http", daemon=True)
    thread.start()
    try:
        ui.run()  # bucle de la interfaz en el hilo principal (tkinter lo exige)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        log.info("agente detenido")
    return 0


def cmd_diagnose(args, *, backend=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # consolas de Windows con página de códigos antigua
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    config = _load(args)
    if config is None:
        return 2
    backend = backend or _backend(args, config)
    if backend is None:
        return 2
    return run_diagnose(config, backend)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--software-token",
        metavar="PEM",
        help="DEMOSTRACIÓN: usar como único certificado el de este archivo PEM (clave + certificado), PIN 1234",
    )
    parser.add_argument(
        "--origin",
        action="append",
        metavar="ORIGEN",
        help="origen permitido (repetible); reemplaza a los del archivo de configuración",
    )
    parser.add_argument("--port", type=int, help="puerto en 127.0.0.1 (reemplaza al del archivo de configuración)")


def main(argv: list[str] | None = None) -> int:
    _attach_parent_console()
    parser = argparse.ArgumentParser(prog="firmadoc-agent", description=__doc__)
    parser.add_argument("--version", action="version", version=f"firmadoc-agent {__version__}")
    parser.add_argument("--config", help="ruta del config.json (por defecto %%APPDATA%%\\FirmadocAgent)")
    sub = parser.add_subparsers(dest="command")
    _add_common(sub.add_parser("run", help="inicia el agente (predeterminado)"))
    _add_common(sub.add_parser("diagnose", help="lista los certificados del token sin pedir el PIN"))
    args = parser.parse_args(argv)
    if args.command == "diagnose":
        return cmd_diagnose(args)
    return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
