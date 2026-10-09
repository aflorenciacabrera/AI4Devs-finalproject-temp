import datetime

import pytest

from firmadoc.certificate_validation import CRL_CACHE, CertificateChecker, CrlCache, extract_cuil
from firmadoc.errors import Forbidden, Unprocessable
from firmadoc.models import RevocationStatus
from firmadoc.trust import load_trust_store, main

DAY = datetime.timedelta(days=1)
CUIL = "20111111112"


@pytest.fixture(autouse=True)
def _cache_limpia():
    """La caché de CRL es global al proceso: ninguna prueba debe heredar la de otra."""
    CRL_CACHE.clear()
    yield
    CRL_CACHE.clear()


def checker(pki, anchors, mode="hard-fail", crls=True, fetching=False, cache=None):
    return CertificateChecker(
        load_trust_store(anchors),
        mode,
        allow_fetching=fetching,
        crls=[pki.ca.crl()] if crls else [],
        crl_cache=cache,
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


# --- caché de CRL (FIRDOC-52) ----------------------------------------------------------------


def _crl_vencida(pki) -> bytes:
    """Una CRL de la AC de prueba cuyo next_update ya pasó."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization

    now = datetime.datetime.now(datetime.UTC)
    builder = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(pki.ca.cert.subject)
        .last_update(now - 10 * DAY)
        .next_update(now - DAY)
    )
    return builder.sign(pki.ca.key, hashes.SHA256()).public_bytes(serialization.Encoding.DER)


def test_una_validacion_con_red_alimenta_la_cache_y_la_siguiente_la_usa_sin_red(pki, anchors):
    """Sin red ni CRL propia, el segundo checker solo puede saber de la revocación por la caché."""
    cache = CrlCache()
    ident = pki.ca.issue("Ana", CUIL)
    pki.ca.revoke(ident)
    sin_cache = checker(pki, anchors, mode="hard-fail", crls=False, cache=CrlCache())
    reject(sin_cache, ident, "certificate_invalid")  # no hay forma de saberlo

    con_red = checker(pki, anchors, mode="hard-fail", crls=True, fetching=True, cache=cache)
    reject(con_red, ident, "certificate_revoked")
    assert len(cache) == 1

    solo_cache = checker(pki, anchors, mode="hard-fail", crls=False, fetching=False, cache=cache)
    reject(solo_cache, ident, "certificate_revoked")
    valido = pki.ca.issue("Bea", CUIL)
    assert solo_cache.validate(valido.der, CUIL).revocation_status == RevocationStatus.GOOD


def test_la_cache_se_alimenta_aunque_la_validacion_falle(pki, anchors):
    cache = CrlCache()
    ajeno = pki.other_ca.issue("Ana", CUIL)
    reject(checker(pki, anchors, crls=True, fetching=True, cache=cache), ajeno, "certificate_untrusted")
    assert len(cache) == 1


def test_sin_consulta_por_red_no_se_alimenta_la_cache(pki, anchors):
    cache = CrlCache()
    ident = pki.ca.issue("Ana", CUIL)
    checker(pki, anchors, crls=True, fetching=False, cache=cache).validate(ident.der, CUIL)
    assert len(cache) == 0


def test_crl_vencida_no_se_entrega_y_se_purga(pki, anchors):
    cache = CrlCache()
    cache.add([_crl_vencida(pki)])
    assert len(cache) == 1
    assert cache.fresh(datetime.datetime.now(datetime.UTC)) == []
    assert len(cache) == 0
    ident = pki.ca.issue("Ana", CUIL)
    err = reject(checker(pki, anchors, crls=False, cache=cache), ident, "certificate_invalid")
    assert "revocación" in err.detail


def test_la_cache_no_guarda_duplicados(pki):
    cache = CrlCache()
    crl = pki.ca.crl()
    assert cache.add([crl, crl]) == 1
    assert cache.add([crl]) == 0
    assert len(cache) == 1


def test_las_crl_locales_siguen_aplicandose_junto_con_la_cache(pki, anchors):
    ident = pki.ca.issue("Ana", CUIL)
    pki.ca.revoke(ident)
    reject(checker(pki, anchors, crls=True, cache=CrlCache()), ident, "certificate_revoked")


def test_el_checker_usa_la_cache_global_por_defecto(pki, anchors):
    c = checker(pki, anchors, crls=True, fetching=True)
    c.validate(pki.ca.issue("Ana", CUIL).der, CUIL)
    assert c.crl_cache is CRL_CACHE and len(CRL_CACHE) == 1


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
