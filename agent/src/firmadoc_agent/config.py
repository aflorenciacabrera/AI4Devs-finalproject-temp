"""Configuración del agente (archivo JSON)."""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PORT = 47123
ORIGIN_RE = re.compile(r"^https?://[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:\d{1,5})?$")
LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class AgentConfig:
    port: int = DEFAULT_PORT
    allowed_origins: tuple[str, ...] = ()
    pkcs11_module: str | None = None
    log_level: str = "INFO"


def data_dir() -> Path:
    """Directorio de datos del usuario (registro, etc.)."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "FirmadocAgent"


def default_config_path() -> Path:
    override = os.environ.get("FIRMADOC_AGENT_CONFIG")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "FirmadocAgent" / "config.json"


def validate_origin(origin: str) -> str:
    if not isinstance(origin, str) or not ORIGIN_RE.match(origin):
        raise ConfigError(
            f"origen inválido: {origin!r}. Deben ser exactos, con el formato "
            "esquema://host[:puerto], sin comodines ni rutas"
        )
    if ":" in origin.split("//", 1)[1] and not 0 < int(origin.rsplit(":", 1)[1]) < 65536:
        raise ConfigError(f"puerto inválido en el origen: {origin!r}")
    return origin.lower()


def parse_config(raw: dict) -> AgentConfig:
    unknown = set(raw) - {"port", "allowed_origins", "pkcs11_module", "log_level"}
    if unknown:
        raise ConfigError(f"claves desconocidas en la configuración: {sorted(unknown)}")
    port = raw.get("port", DEFAULT_PORT)
    if not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535:
        raise ConfigError(f"port inválido: {port!r} (debe estar entre 1024 y 65535)")
    origins = raw.get("allowed_origins", [])
    if not isinstance(origins, list):
        raise ConfigError("allowed_origins debe ser una lista")
    module = raw.get("pkcs11_module")
    if module is not None and not isinstance(module, str):
        raise ConfigError("pkcs11_module debe ser una ruta (texto)")
    level = str(raw.get("log_level", "INFO")).upper()
    if level not in LOG_LEVELS:
        raise ConfigError(f"log_level inválido: {level!r}")
    return AgentConfig(
        port=port,
        allowed_origins=tuple(validate_origin(o) for o in origins),
        pkcs11_module=module,
        log_level=level,
    )


def load_config(path: Path | None = None) -> AgentConfig:
    path = path or default_config_path()
    if not path.exists():
        return AgentConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))  # tolera el BOM del Bloc de notas
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError(f"no se pudo leer la configuración {path}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"la configuración {path} debe ser un objeto JSON")
    return parse_config(raw)
