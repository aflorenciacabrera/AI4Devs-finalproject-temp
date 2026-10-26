import pytest

from firmadoc_agent.errors import AgentError
from firmadoc_agent.selftest import self_test
from firmadoc_agent.testing import SoftwareBackend
from helpers import soft_token


def run(backend, pin="1234", **kw):
    lines: list[str] = []
    ok = self_test(backend, pin, out=lines.append, **kw)
    return ok, "\n".join(lines)


def test_autoprueba_correcta_con_un_solo_login():
    backend = SoftwareBackend([soft_token()])
    ok, text = run(backend, batch=3)
    assert ok
    assert text.count("OK: RSA PKCS#1 v1.5") == 3
    assert "RESULTADO: CORRECTO" in text
    assert backend.login_attempts == 1  # un solo ingreso de PIN para todo el lote


def test_pin_incorrecto_es_un_error_y_un_unico_intento():
    backend = SoftwareBackend([soft_token()])
    with pytest.raises(AgentError) as e:
        run(backend, pin="0000")
    assert e.value.code == "pin_incorrect"
    assert backend.login_attempts == 1


def test_detecta_una_firma_que_no_verifica():
    class Mala(SoftwareBackend):
        def sign(self, certificate_id, pin, digests):
            return [b"\x00" * 256 for _ in digests]

    ok, text = run(Mala([soft_token()]))
    assert not ok
    assert "no verifica" in text and "RESULTADO: FALLÓ" in text


def test_certificado_inexistente():
    ok, text = run(SoftwareBackend([soft_token()]), certificate_id="zzz")
    assert not ok and "no existe el certificado" in text
