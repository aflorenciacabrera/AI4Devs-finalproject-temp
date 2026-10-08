import logging
import time
import uuid

import pytest
from pydantic import ValidationError

from firmadoc import signing_token
from firmadoc.config import Settings
from firmadoc.errors import Unauthorized

SECRET = "s" * 40
RID = uuid.uuid4()


def issue(**kw):
    return signing_token.issue(kw.pop("secret", SECRET), kw.pop("rid", RID), kw.pop("ttl", 3600), **kw)


def test_token_valido():
    payload = signing_token.verify(SECRET, issue(), RID)
    assert payload["rid"] == str(RID)
    assert payload["exp"] > time.time()


def test_token_de_otra_solicitud():
    with pytest.raises(Unauthorized) as e:
        signing_token.verify(SECRET, issue(), uuid.uuid4())
    assert e.value.code == "invalid_token"


def test_token_vencido():
    token = issue(ttl=60, now=time.time() - 3600)
    with pytest.raises(Unauthorized):
        signing_token.verify(SECRET, token, RID)


def test_vence_exactamente_en_el_limite():
    now = 1_000_000.0
    token = issue(ttl=10, now=now)
    assert signing_token.verify(SECRET, token, RID, now=now + 9)
    with pytest.raises(Unauthorized):
        signing_token.verify(SECRET, token, RID, now=now + 10)


# No se altera el último carácter: en base64url solo aporta 4 bits y varios caracteres decodifican igual.
@pytest.mark.parametrize("position", [0, 5, -2, -10])
def test_token_alterado_un_solo_caracter(position):
    token = issue()
    index = position % len(token)
    swapped = "A" if token[index] != "A" else "B"
    tampered = token[:index] + swapped + token[index + 1 :]
    with pytest.raises(Unauthorized):
        signing_token.verify(SECRET, tampered, RID)


def test_otro_secreto():
    with pytest.raises(Unauthorized):
        signing_token.verify("t" * 40, issue(), RID)


@pytest.mark.parametrize("token", ["", "abc", "a.b.c", ".", "..", "no es base64.firma", "e30.e30"])
def test_formatos_invalidos(token):
    with pytest.raises(Unauthorized):
        signing_token.verify(SECRET, token, RID)


def test_el_token_no_revela_el_secreto_ni_es_reutilizable_como_api_key():
    token = issue()
    assert SECRET not in token
    assert "." in token and "+" not in token and "/" not in token  # base64url


def test_secreto_demasiado_corto_no_arranca():
    with pytest.raises(ValidationError) as e:
        Settings(signing_secret="corto")
    assert "al menos 32 caracteres" in str(e.value)


def test_secreto_vacio_equivale_a_no_configurado():
    assert Settings(signing_secret="").signing_secret is None


def test_secreto_configurado_se_usa_tal_cual():
    assert signing_token.secret_for(Settings(signing_secret=SECRET)) == SECRET


def test_sin_secreto_usa_uno_efimero_estable_y_advierte(caplog, monkeypatch):
    monkeypatch.setattr(signing_token, "_ephemeral_secret", None)
    settings = Settings(signing_secret=None)
    with caplog.at_level(logging.WARNING, logger="firmadoc"):
        first = signing_token.secret_for(settings)
        second = signing_token.secret_for(settings)
    assert first == second and len(first) >= 32
    assert sum("secreto efímero" in r.message for r in caplog.records) == 1
