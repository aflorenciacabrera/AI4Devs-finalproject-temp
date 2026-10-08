import datetime

import pytest

from firmadoc.certificate_validation import CertificateChecker, extract_cuil
from firmadoc.errors import Forbidden, Unprocessable
from firmadoc.models import RevocationStatus
from firmadoc.trust import load_trust_store, main

DAY = datetime.timedelta(days=1)
CUIL = "20111111112"


def checker(pki, anchors, mode="hard-fail", crls=True):
    return CertificateChecker(
        load_trust_store(anchors),
        mode,
        allow_fetching=False,
        crls=[pki.ca.crl()] if crls else [],
    )


def reject(c, identity, code, exc=Unprocessable, expected=CUIL):
    with pytest.raises(exc) as info:
        c.validate(identity.der, expected)
    assert info.value.code == code
    return info.value


# --- anclas ---------------------------------------------------------------------------------


def test_anclas_raiz_e_intermedia(anchors):
    store = load_trust_store(anchors)
    assert len(store.roots) == 1
    assert len(store.intermediates) == 1


def test_directorio_vacio_rechaza_todo(pki, tmp_path):
    empty = tmp_path / "vacio"
    empty.mkdir()
    c = CertificateChecker(load_trust_store(empty), "hard-fail", allow_fetching=False)
    reject(c, pki.ca.issue("Ana", CUIL), "certificate_untrusted")


def test_comando_lista_huellas(anchors, monkeypatch, capsys):
    monkeypatch.setenv("FIRMADOC_TRUST_DIR", str(anchors))
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "RAIZ" in out and "Raiz de Prueba" in out and "AC de Prueba" in out
    assert len([ln for ln in out.splitlines() if ln.strip()]) == 2
    assert all(len(ln.split()[1]) == 64 for ln in out.splitlines() if ln.strip())


# --- cadena -------------------------------------------------------------------------------


def test_certificado_valido(pki, anchors):
    ident = pki.ca.issue("Ana", CUIL)
    result = checker(pki, anchors).validate(ident.der, CUIL)
    assert result.cuil == CUIL
    assert result.revocation_status == RevocationStatus.GOOD
    assert result.serial_number == str(ident.cert.serial_number)


def test_otra_ac_no_es_confiable(pki, anchors):
    reject(checker(pki, anchors), pki.other_ca.issue("Ana", CUIL), "certificate_untrusted")


# --- vigencia y uso -----------------------------------------------------------------------


def test_vencido(pki, anchors):
    now = datetime.datetime.now(datetime.UTC)
    ident = pki.ca.issue("Ana", CUIL, not_before=now - 60 * DAY, not_after=now - DAY)
    reject(checker(pki, anchors), ident, "certificate_expired")


def test_todavia_no_vigente(pki, anchors):
    now = datetime.datetime.now(datetime.UTC)
    ident = pki.ca.issue("Ana", CUIL, not_before=now + DAY, not_after=now + 30 * DAY)
    reject(checker(pki, anchors), ident, "certificate_invalid")


def test_uso_de_clave_inadecuado(pki, anchors):
    reject(checker(pki, anchors), pki.ca.issue("Ana", CUIL, digital_signature=False), "certificate_invalid")


def test_clave_rsa_debil(pki, anchors):
    reject(checker(pki, anchors), pki.ca.issue("Ana", CUIL, key_size=1024), "certificate_invalid")


def test_basura_no_es_certificado(pki, anchors):
    with pytest.raises(Unprocessable) as info:
        checker(pki, anchors).validate(b"no soy un certificado", CUIL)
    assert info.value.code == "certificate_invalid"


# --- revocación ---------------------------------------------------------------------------


def test_revocado(pki, anchors):
    ident = pki.ca.issue("Ana", CUIL)
    pki.ca.revoke(ident)
    reject(checker(pki, anchors), ident, "certificate_revoked")


def test_soft_fail_sin_crl_acepta_con_estado_desconocido(pki, anchors):
    ident = pki.ca.issue("Ana", CUIL)
    result = checker(pki, anchors, mode="soft-fail", crls=False).validate(ident.der, CUIL)
    assert result.revocation_status == RevocationStatus.UNKNOWN


def test_hard_fail_sin_crl_rechaza(pki, anchors):
    ident = pki.ca.issue("Ana", CUIL)
    err = reject(checker(pki, anchors, mode="hard-fail", crls=False), ident, "certificate_invalid")
    assert "revocación" in err.detail


def test_soft_fail_igual_rechaza_si_esta_revocado(pki, anchors):
    ident = pki.ca.issue("Ana", CUIL)
    pki.ca.revoke(ident)
    reject(checker(pki, anchors, mode="soft-fail"), ident, "certificate_revoked")


def test_modo_off_no_consulta_revocacion(pki, anchors):
    ident = pki.ca.issue("Ana", CUIL)
    pki.ca.revoke(ident)
    result = checker(pki, anchors, mode="off").validate(ident.der, CUIL)
    assert result.revocation_status == RevocationStatus.UNKNOWN


def test_soft_fail_no_acepta_cadena_invalida(pki, anchors):
    reject(checker(pki, anchors, mode="soft-fail", crls=False), pki.other_ca.issue("Ana", CUIL), "certificate_untrusted")


# --- CUIL ---------------------------------------------------------------------------------


def test_cuil_con_guiones_coincide(pki, anchors):
    ident = pki.ca.issue("Ana", CUIL)
    assert checker(pki, anchors).validate(ident.der, "20-11111111-2").cuil == CUIL


def test_cuil_distinto(pki, anchors):
    reject(checker(pki, anchors), pki.ca.issue("Ana", CUIL), "cuil_mismatch", Forbidden, "20999999995")


def test_certificado_sin_cuil(pki, anchors):
    reject(checker(pki, anchors), pki.ca.issue("Ana", None), "cuil_mismatch", Forbidden)


def test_cuil_se_evalua_despues_de_la_cadena(pki, anchors):
    """Un certificado no confiable no debe revelar si el CUIL coincide."""
    reject(checker(pki, anchors), pki.other_ca.issue("Ana", "20999999995"), "certificate_untrusted")


def test_extract_cuil(pki):
    from asn1crypto import x509 as ax509

    assert extract_cuil(ax509.Certificate.load(pki.ca.issue("Ana", CUIL).der)) == CUIL
    assert extract_cuil(ax509.Certificate.load(pki.ca.issue("Ana", None).der)) is None
