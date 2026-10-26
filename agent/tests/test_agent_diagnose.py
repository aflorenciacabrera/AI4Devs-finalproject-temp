import json

from firmadoc_agent.__main__ import main
from firmadoc_agent.config import AgentConfig
from firmadoc_agent.diagnose import EXIT_LIBRARY, EXIT_NO_TOKEN, EXIT_OK, run_diagnose
from firmadoc_agent.errors import pkcs11_unavailable
from firmadoc_agent.testing import SoftwareBackend
from helpers import ca_token, soft_token


def diagnose(backend, config=None):
    lines: list[str] = []
    code = run_diagnose(config or AgentConfig(pkcs11_module="modulo.dll"), backend, lines.append)
    return code, "\n".join(lines)


def test_lista_certificados_y_el_cuil_sin_pedir_pin():
    backend = SoftwareBackend([soft_token(), ca_token()])
    code, text = diagnose(backend)
    assert code == EXIT_OK
    assert "Biblioteca PKCS#11 cargada correctamente" in text
    assert "Certificado de usuario" in text and "Certificado de AC" in text
    assert "Juan Perez" in text
    assert "serialNumber del sujeto (CUIL): CUIL 20111111112" in text  # formato real del CUIL
    assert "Uso de clave: digital_signature, non_repudiation" in text
    assert backend.login_attempts == 0  # nunca abre sesión autenticada


def test_la_ac_no_muestra_cuil():
    _code, text = diagnose(SoftwareBackend([ca_token()]))
    assert "serialNumber del sujeto" not in text


def test_sin_token():
    code, text = diagnose(SoftwareBackend([]))
    assert code == EXIT_NO_TOKEN
    assert "No hay ningún token" in text


def test_biblioteca_inexistente_sugiere_revisar_la_arquitectura():
    class Roto(SoftwareBackend):
        def inspect(self):
            raise pkcs11_unavailable("no se pudo cargar la biblioteca PKCS#11 x.dll")

    code, text = diagnose(Roto([]))
    assert code == EXIT_LIBRARY
    assert "arquitectura" in text and "32 o 64 bits" in text


def test_error_inesperado_no_termina_con_traza():
    class Peor(SoftwareBackend):
        def inspect(self):
            raise RuntimeError("boom")

    code, text = diagnose(Peor([]))
    assert code == EXIT_LIBRARY and "boom" in text


def test_comando_diagnose_con_modulo_inexistente(tmp_path, capsys):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"pkcs11_module": str(tmp_path / "no-existe.dll")}))
    code = main(["--config", str(cfg), "diagnose"])
    out = capsys.readouterr().out
    assert code != 0
    assert "no se pudo cargar la biblioteca" in out and "arquitectura" in out
