"""Anclas de la infraestructura de firma digital argentina incluidas en `backend/trust/` (FIRDOC-49)."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding
from pyhanko_certvalidator import CertificateValidator, ValidationContext

from firmadoc.trust import _read_directory

TRUST_DIR = Path(__file__).resolve().parents[1] / "backend" / "trust"
ROOT_FINGERPRINT = "975c663546ed8923d132256f2f3300838e3fe01e04e37739e954ff931e9f8ba4"
INTERMEDIATE_FINGERPRINT = "b3c367a4e3842854c8820a9eda492318e2ca0ecf9abb8130de8f6dcd53ac2510"
ROOT_FILE = "ac-raiz-republica-argentina-2016.crt"
INTERMEDIATE_FILE = "ac-firma-digital-onti-2026.crt"


def test_el_repo_trae_la_raiz_y_la_intermedia_con_sus_huellas():
    store = _read_directory(TRUST_DIR)
    roots = [c for c in store.certs if c.is_root]
    intermediates = [c for c in store.certs if not c.is_root]
    assert [c.fingerprint for c in roots] == [ROOT_FINGERPRINT]
    assert [c.fingerprint for c in intermediates] == [INTERMEDIATE_FINGERPRINT]
    assert "AC Ra" in roots[0].subject and "blica Argentina" in roots[0].subject
    assert "Autoridad Certificante de Firma Digital" in intermediates[0].subject


def test_cada_ancla_esta_en_su_propio_archivo_pem():
    root = x509.load_pem_x509_certificates((TRUST_DIR / ROOT_FILE).read_bytes())
    intermediate = x509.load_pem_x509_certificates((TRUST_DIR / INTERMEDIATE_FILE).read_bytes())
    assert len(root) == 1 and len(intermediate) == 1
    assert root[0].subject == root[0].issuer
    assert intermediate[0].issuer == root[0].subject


def test_la_intermedia_esta_firmada_por_la_raiz():
    root = x509.load_pem_x509_certificate((TRUST_DIR / ROOT_FILE).read_bytes())
    intermediate = x509.load_pem_x509_certificate((TRUST_DIR / INTERMEDIATE_FILE).read_bytes())
    root.public_key().verify(  # lanza InvalidSignature si no corresponde
        intermediate.signature,
        intermediate.tbs_certificate_bytes,
        padding.PKCS1v15(),
        intermediate.signature_hash_algorithm,
    )


def test_la_cadena_intermedia_raiz_valida_sin_red():
    store = _read_directory(TRUST_DIR)
    context = ValidationContext(
        trust_roots=store.roots,
        moment=datetime(2026, 10, 9, tzinfo=UTC),
        allow_fetching=False,
        revocation_mode="soft-fail",
    )
    validator = CertificateValidator(store.intermediates[0], validation_context=context)
    path = asyncio.run(validator.async_validate_usage(set()))
    assert len(path) == 2  # intermedia + raíz


def test_el_readme_documenta_las_huellas_y_las_fuentes():
    text = (TRUST_DIR / "README.md").read_text(encoding="utf8")
    assert ROOT_FINGERPRINT in text and INTERMEDIATE_FINGERPRINT in text
    assert "acraiz.gov.ar" in text and "pki.jgm.gov.ar" in text
    assert "-fingerprint -sha256" in text
