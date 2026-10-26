import json

import pytest

from firmadoc_agent.config import (
    DEFAULT_PORT,
    ConfigError,
    default_config_path,
    load_config,
    parse_config,
)


def test_sin_archivo_usa_valores_por_defecto(tmp_path):
    cfg = load_config(tmp_path / "no-existe.json")
    assert cfg.port == DEFAULT_PORT
    assert cfg.allowed_origins == ()
    assert cfg.pkcs11_module is None


def test_archivo_valido(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "port": 50000,
                "allowed_origins": ["https://Firmadoc.Example.org", "http://localhost:4200"],
                "pkcs11_module": "C:/Windows/System32/eps2003csp11.dll",
                "log_level": "debug",
            }
        )
    )
    cfg = load_config(path)
    assert cfg.port == 50000
    assert cfg.allowed_origins == ("https://firmadoc.example.org", "http://localhost:4200")
    assert cfg.log_level == "DEBUG"


@pytest.mark.parametrize(
    "origin",
    [
        "https://*.example.org",
        "https://example.org/ruta",
        "example.org",
        "ftp://example.org",
        "https://example.org:99999",
        "*",
        "null",
        "",
    ],
)
def test_origen_invalido(origin):
    with pytest.raises(ConfigError, match="esquema://host|puerto"):
        parse_config({"allowed_origins": [origin]})


@pytest.mark.parametrize("port", [0, 80, 70000, "47123", True])
def test_puerto_invalido(port):
    with pytest.raises(ConfigError):
        parse_config({"port": port})


def test_clave_desconocida_no_se_ignora():
    with pytest.raises(ConfigError, match="desconocidas"):
        parse_config({"puerto": 5000})


def test_json_roto(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{no es json")
    with pytest.raises(ConfigError):
        load_config(path)


def test_ruta_por_variable_de_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("FIRMADOC_AGENT_CONFIG", str(tmp_path / "otra.json"))
    assert default_config_path() == tmp_path / "otra.json"
