"""Token de software (demostración): carga del PEM, backend y opciones `--software-token`, `--origin`, `--port`."""

import argparse
import http.client
import json
import logging
import socket

import pytest
from cryptography.hazmat.primitives import serialization

from firmadoc_agent.__main__ import cmd_run, main
from firmadoc_agent.software_token import (
    SOFTWARE_PIN,
    SoftwareTokenError,
    load_software_token,
    software_backend,
)
from firmadoc_agent.testing import FakeUI
from helpers import make_cert

ORIGIN = "http://localhost:8000"


@pytest.fixture(autouse=True)
def datos_del_usuario(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("FIRMADOC_AGENT_CONFIG", str(tmp_path / "no-existe.json"))  # sin config.json
    yield
    logger = logging.getLogger("firmadoc_agent")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def pem(tmp_path):
    key, cert = make_cert("Firmante de Prueba", cuil="20000000001")
    path = tmp_path / "firmante.pem"
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
        + cert.public_bytes(serialization.Encoding.PEM)
    )
    return path


def test_carga_el_certificado_y_la_clave(pem):
    token = load_software_token(pem)
    assert token.cert_id.startswith("SOFT:")
    backend = software_backend(pem)
    certs = backend.list_certificates()
    assert len(certs) == 1 and "Firmante de Prueba" in certs[0].subject
    assert backend.pin == SOFTWARE_PIN


@pytest.mark.parametrize(
    "content, expected",
    [
        (b"nada", "no contiene un certificado"),
        (b"-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n", "clave privada"),
    ],
)
def test_pem_invalido(tmp_path, content, expected):
    path = tmp_path / "malo.pem"
    path.write_bytes(content)
    with pytest.raises(SoftwareTokenError, match=expected):
        load_software_token(path)


def test_archivo_inexistente(tmp_path):
    with pytest.raises(SoftwareTokenError, match="no se pudo leer"):
        load_software_token(tmp_path / "no.pem")


def test_run_con_token_de_software_sin_config(pem):
    """`run --software-token --origin --port` sin config.json: atiende desde ese origen y firma con PIN 1234."""
    port = free_port()
    seen = {}

    class Ui(FakeUI):
        def run(self):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.request("GET", "/certificates", headers={"Origin": ORIGIN})
            resp = conn.getresponse()
            seen["status"], seen["body"] = resp.status, json.loads(resp.read())
            conn.request("GET", "/certificates", headers={"Origin": "http://otro.test"})
            seen["other"] = conn.getresponse().status
            conn.close()

    args = argparse.Namespace(
        config=None, command="run", software_token=str(pem), origin=[ORIGIN], port=port
    )
    assert cmd_run(args, ui=Ui(pin=SOFTWARE_PIN)) == 0
    assert seen["status"] == 200
    assert seen["body"]["certificates"][0]["subject"].count("Firmante de Prueba") == 1
    assert seen["other"] == 403


def test_run_con_pem_invalido_no_arranca(tmp_path, capsys):
    bad = tmp_path / "malo.pem"
    bad.write_bytes(b"nada")
    assert main(["run", "--software-token", str(bad), "--origin", ORIGIN, "--port", str(free_port())]) == 2
    assert "Token de software inválido" in capsys.readouterr().err


def test_diagnose_con_token_de_software(pem, capsys):
    assert main(["diagnose", "--software-token", str(pem)]) == 0
    out = capsys.readouterr().out
    assert "Firmante de Prueba" in out


def test_port_invalido(pem, capsys):
    assert main(["run", "--software-token", str(pem), "--port", "80"]) == 2
    assert "port inválido" in capsys.readouterr().err
