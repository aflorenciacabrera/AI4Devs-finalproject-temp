"""Tokens de prueba en SoftHSM (PKCS#11 por software). Solo se usan si `SOFTHSM2_MODULE` está definida."""

import os
import subprocess
from pathlib import Path

import pkcs11
from cryptography.hazmat.primitives import serialization
from pkcs11 import Attribute, CertificateType, KeyType, ObjectClass

USER_PIN = "1234"
SO_PIN = "5678"


def _bytes(n: int) -> bytes:
    return n.to_bytes((n.bit_length() + 7) // 8, "big")


def configure(base: Path) -> None:
    tokens = base / "tokens"
    tokens.mkdir(parents=True, exist_ok=True)
    conf = base / "softhsm2.conf"
    conf.write_text(f"directories.tokendir = {tokens}\nobjectstore.backend = file\nlog.level = ERROR\n")
    os.environ["SOFTHSM2_CONF"] = str(conf)  # debe fijarse antes de cargar la biblioteca


def init_token(label: str) -> None:
    util = os.environ.get("SOFTHSM2_UTIL", "softhsm2-util")
    result = subprocess.run(
        [
            util, "--module", os.environ["SOFTHSM2_MODULE"], "--init-token", "--free",
            "--label", label, "--so-pin", SO_PIN, "--pin", USER_PIN,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"softhsm2-util falló ({result.returncode}): {result.stdout}{result.stderr}")


def import_identity(module: str, label: str, cka_id: bytes, key, cert_der: bytes) -> None:
    """Importa al token una clave privada RSA y su certificado (con el mismo CKA_ID)."""
    token = pkcs11.lib(module).get_token(token_label=label)
    n = key.private_numbers()
    with token.open(rw=True, user_pin=USER_PIN) as session:
        session.create_object(
            {
                Attribute.CLASS: ObjectClass.PRIVATE_KEY,
                Attribute.KEY_TYPE: KeyType.RSA,
                Attribute.TOKEN: True,
                Attribute.PRIVATE: True,
                Attribute.SENSITIVE: True,
                Attribute.SIGN: True,
                Attribute.ID: cka_id,
                Attribute.LABEL: "clave de firma",
                Attribute.MODULUS: _bytes(n.public_numbers.n),
                Attribute.PUBLIC_EXPONENT: _bytes(n.public_numbers.e),
                Attribute.PRIVATE_EXPONENT: _bytes(n.d),
                Attribute.PRIME_1: _bytes(n.p),
                Attribute.PRIME_2: _bytes(n.q),
                Attribute.EXPONENT_1: _bytes(n.dmp1),
                Attribute.EXPONENT_2: _bytes(n.dmq1),
                Attribute.COEFFICIENT: _bytes(n.iqmp),
            }
        )
        import_certificate(session, cka_id, cert_der, "certificado")


def import_certificate(session, cka_id: bytes, cert_der: bytes, label: str) -> None:
    from cryptography import x509

    cert = x509.load_der_x509_certificate(cert_der)
    session.create_object(
        {
            Attribute.CLASS: ObjectClass.CERTIFICATE,
            Attribute.CERTIFICATE_TYPE: CertificateType.X_509,
            Attribute.TOKEN: True,
            Attribute.ID: cka_id,
            Attribute.LABEL: label,
            Attribute.SUBJECT: cert.subject.public_bytes(),
            Attribute.VALUE: cert_der,
        }
    )


def import_ca(module: str, label: str, cka_id: bytes, cert_der: bytes) -> None:
    token = pkcs11.lib(module).get_token(token_label=label)
    with token.open(rw=True, user_pin=USER_PIN) as session:
        import_certificate(session, cka_id, cert_der, "AC")


def der(cert) -> bytes:
    return cert.public_bytes(serialization.Encoding.DER)
