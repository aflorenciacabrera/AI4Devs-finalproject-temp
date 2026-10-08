"""Punto de entrada: `firmadoc-agent [run|diagnose] [--config RUTA] [--version]`."""

import argparse
import os
import sys
import threading
from pathlib import Path

from . import __version__
from .config import AgentConfig, ConfigError, data_dir, default_config_path, load_config
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
    path = Path(args.config) if args.config else default_config_path()
    try:
        return load_config(path)
    except ConfigError as e:
        _say(f"Configuración inválida: {e}")
        return None


def cmd_run(args, *, ui=None, backend=None) -> int:
    config = _load(args)
    if config is None:
        return 2
    log = setup_logging(config.log_level, data_dir() / "agent.log")
    if not config.allowed_origins:
        log.warning("la lista de orígenes permitidos está vacía: se rechazará todo pedido")
    if not config.pkcs11_module:
        log.warning("'pkcs11_module' no está configurado: no se podrá acceder al token")

    backend = backend or Pkcs11Backend(config.pkcs11_module)
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
    return run_diagnose(config, backend or Pkcs11Backend(config.pkcs11_module))


def main(argv: list[str] | None = None) -> int:
    _attach_parent_console()
    parser = argparse.ArgumentParser(prog="firmadoc-agent", description=__doc__)
    parser.add_argument("--version", action="version", version=f"firmadoc-agent {__version__}")
    parser.add_argument("--config", help="ruta del config.json (por defecto %%APPDATA%%\\FirmadocAgent)")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="inicia el agente (predeterminado)")
    sub.add_parser("diagnose", help="lista los certificados del token sin pedir el PIN")
    args = parser.parse_args(argv)
    if args.command == "diagnose":
        return cmd_diagnose(args)
    return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
