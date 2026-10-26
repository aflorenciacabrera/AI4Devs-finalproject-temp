"""Mapeo de errores y política de PIN del backend PKCS#11 con un token falso (sin SoftHSM).

SoftHSM no emula el bloqueo del PIN ni el aviso de último intento; aquí se verifican contra un
token que lanza las mismas excepciones de python-pkcs11 que lanzaría uno real.
"""

import pytest
from pkcs11 import TokenFlag
from pkcs11 import exceptions as p11

from firmadoc_agent.errors import AgentError
from firmadoc_agent.pkcs11_backend import Pkcs11Backend

SERIAL = "0123456789abcdef"
CERT_ID = f"{SERIAL}:01"


class FakeKey:
    def __init__(self, fail=None):
        self.fail = fail
        self.signed = 0

    def sign(self, data, mechanism):
        if self.fail:
            raise self.fail
        self.signed += 1
        return b"\x01" * 256


class FakeSession:
    def __init__(self, token):
        self.token = token

    def __enter__(self):
        self.token.open_sessions += 1
        return self

    def __exit__(self, *exc):
        self.token.open_sessions -= 1

    def get_key(self, object_class, id):
        if self.token.no_key:
            raise p11.NoSuchKey()
        return self.token.key


class FakeToken:
    serial = SERIAL.encode()  # python-pkcs11 devuelve bytes
    label = "Token falso"

    def __init__(self, *, login_error=None, flags=TokenFlag.TOKEN_INITIALIZED, key=None, no_key=False):
        self.login_error = login_error
        self.flags = flags
        self.key = key or FakeKey()
        self.no_key = no_key
        self.opens = 0
        self.open_sessions = 0

    def open(self, user_pin=None, rw=False):
        self.opens += 1
        if user_pin is not None and self.login_error:
            raise self.login_error
        return FakeSession(self)


class FakeBackend(Pkcs11Backend):
    def __init__(self, tokens):
        super().__init__("modulo-falso")
        self._fake = tokens

    def tokens(self):
        return self._fake


def sign(token, pin="1234"):
    return FakeBackend([token]).sign(CERT_ID, pin, [bytes(32)])


def test_un_unico_login_por_pedido_aunque_falle():
    token = FakeToken(login_error=p11.PinIncorrect())
    with pytest.raises(AgentError) as e:
        sign(token)
    assert e.value.code == "pin_incorrect" and e.value.status == 401
    assert token.opens == 1  # no hay reintentos automáticos
    assert token.open_sessions == 0


def test_pin_bloqueado():
    with pytest.raises(AgentError) as e:
        sign(FakeToken(login_error=p11.PinLocked()))
    assert (e.value.code, e.value.status) == ("pin_locked", 423)


def test_pin_expirado():
    with pytest.raises(AgentError) as e:
        sign(FakeToken(login_error=p11.PinExpired()))
    assert e.value.code == "pin_expired"


def test_token_retirado_durante_la_firma():
    with pytest.raises(AgentError) as e:
        sign(FakeToken(login_error=p11.TokenNotPresent()))
    assert e.value.code == "token_not_found"


def test_otro_error_del_token_se_informa_sin_trazas():
    with pytest.raises(AgentError) as e:
        sign(FakeToken(key=FakeKey(fail=p11.PKCS11Error("CKR_DEVICE_ERROR"))))
    assert e.value.code == "pkcs11_error" and e.value.status == 500


def test_clave_privada_inexistente():
    with pytest.raises(AgentError) as e:
        sign(FakeToken(no_key=True))
    assert e.value.code == "private_key_not_found"


def test_la_sesion_se_cierra_tras_firmar():
    token = FakeToken()
    assert len(sign(token)) == 1
    assert token.open_sessions == 0


def test_ultimo_intento_se_lee_de_las_banderas_del_token():
    ultimo = FakeToken(flags=TokenFlag.TOKEN_INITIALIZED | TokenFlag.USER_PIN_FINAL_TRY)
    assert FakeBackend([ultimo]).final_try(CERT_ID) is True
    assert FakeBackend([FakeToken()]).final_try(CERT_ID) is False


def test_serie_en_bytes_se_normaliza():
    assert FakeBackend([FakeToken()])._find_token(SERIAL) is not None


def test_slots_sin_inicializar_se_ignoran():
    class Slot:
        def __init__(self, token):
            self._t = token

        def get_token(self):
            return self._t

    class Lib:
        def get_slots(self, token_present):
            return [Slot(FakeToken(flags=TokenFlag(0))), Slot(FakeToken())]

    backend = Pkcs11Backend("x")
    backend._lib = Lib()
    assert len(backend.tokens()) == 1
