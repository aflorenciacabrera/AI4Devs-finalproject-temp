import argparse
import http.client
import json
import logging
import socket

import pytest

from conftest import hash_item
from firmadoc_agent import __version__
from firmadoc_agent.__main__ import cmd_run, main
from firmadoc_agent.logs import BACKUP_COUNT, MAX_BYTES, setup_logging
from firmadoc_agent.service import AgentService
from firmadoc_agent.testing import FakeUI, SoftwareBackend
from helpers import soft_token

ORIGIN = "https://firmadoc.example.org"


@pytest.fixture(autouse=True)
def datos_del_usuario(tmp_path, monkeypatch):
    """El registro va al directorio de datos del usuario: aislarlo en cada prueba."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    yield
    logger = logging.getLogger("firmadoc_agent")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def write_config(tmp_path, **values) -> str:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(values))
    return str(path)


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_configuracion_invalida_no_arranca(tmp_path, capsys):
    cfg = write_config(tmp_path, allowed_origins=["https://*.example.org"])
    assert main(["--config", cfg, "run"]) == 2
    assert "Configuración inválida" in capsys.readouterr().err


def test_segundo_arranque_con_el_puerto_ocupado(tmp_path, capsys):
    port = free_port()
    cfg = write_config(tmp_path, port=port, allowed_origins=[ORIGIN])
    with socket.socket() as ocupante:
        ocupante.bind(("127.0.0.1", port))
        ocupante.listen()
        assert main(["--config", cfg, "run"]) == 1
    err = capsys.readouterr().err
    assert "Ya hay una instancia del agente o el puerto está en uso" in err


def test_arranque_completo_atiende_pedidos(tmp_path):
    """`run` con la configuración del archivo: servidor arriba mientras corre el bucle de la UI."""
    port = free_port()
    cfg = write_config(tmp_path, port=port, allowed_origins=[ORIGIN])
    token = soft_token()
    seen = {}

    class Ui(FakeUI):
        def run(self):  # reemplaza el bucle de tkinter: hace un pedido y termina
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.request("GET", "/certificates", headers={"Origin": ORIGIN})
            resp = conn.getresponse()
            seen["status"], seen["body"] = resp.status, json.loads(resp.read())
            conn.close()

    args = argparse.Namespace(config=cfg, command="run")
    assert cmd_run(args, ui=Ui(), backend=SoftwareBackend([token])) == 0
    assert seen["status"] == 200
    assert seen["body"]["certificates"][0]["id"] == token.cert_id
    with pytest.raises(OSError):  # el servidor se cerró al terminar
        socket.create_connection(("127.0.0.1", port), timeout=1)


# --- registro ------------------------------------------------------------------------------


def test_el_registro_no_contiene_pin_firmas_ni_hashes(tmp_path):
    log_file = tmp_path / "agent.log"
    setup_logging("DEBUG", log_file)
    token = soft_token()
    pin = "s3cretPIN-9"
    item = hash_item("resolucion-0457.pdf", "c1", b"datos")
    result = AgentService(SoftwareBackend([token], pin=pin), FakeUI(pin=pin)).sign(
        {"certificate_id": token.cert_id, "items": [item]}, origin=ORIGIN
    )
    for handler in logging.getLogger("firmadoc_agent").handlers:
        handler.flush()
    text = log_file.read_text(encoding="utf-8")
    assert "resolucion-0457.pdf" in text and ORIGIN in text and "firma ok" in text
    assert pin not in text
    assert item["hash_to_sign"] not in text  # el hash completo no se registra
    assert result["signatures"][0]["signature_base64"] not in text


def test_rotacion_del_registro(tmp_path):
    log_file = tmp_path / "agent.log"
    logger = setup_logging("INFO", log_file)
    handler = next(h for h in logger.handlers if hasattr(h, "maxBytes"))
    assert (handler.maxBytes, handler.backupCount) == (MAX_BYTES, BACKUP_COUNT)
    assert (MAX_BYTES, BACKUP_COUNT) == (1024 * 1024, 3)
    linea = "x" * 1000
    for _ in range(5000):  # ~5 MB: fuerza varias rotaciones
        logger.info(linea)
    handler.flush()
    archivos = sorted(tmp_path.glob("agent.log*"))
    assert len(archivos) <= 4  # el actual + 3 copias como máximo
    assert all(p.stat().st_size <= MAX_BYTES + 2000 for p in archivos)
