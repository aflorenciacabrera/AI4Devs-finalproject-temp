"""Certificados de prueba para los tests del agente (sin valor legal)."""

import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from firmadoc_agent.testing import SoftwareToken

CUIL = "20111111112"


def make_cert(cn: str, *, ca: bool = False, cuil: str | None = CUIL, issuer=None, issuer_key=None):
    key = rsa.generate_private_key(65537, 2048)
    attrs = [x509.NameAttribute(NameOID.COMMON_NAME, cn)]
    if cuil:
        attrs.append(x509.NameAttribute(NameOID.SERIAL_NUMBER, f"CUIL {cuil}"))
    name = x509.Name(attrs)
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer or name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                not ca, not ca, False, False, False, ca, ca, False, False
            ),
            critical=True,
        )
        .sign(issuer_key or key, hashes.SHA256())
    )
    return key, cert


def soft_token(cert_id: str = "a1b2", cn: str = "Juan Perez") -> SoftwareToken:
    key, cert = make_cert(cn)
    return SoftwareToken(cert_id, cert.public_bytes(serialization.Encoding.DER), key)


def ca_token(cert_id: str = "ca01") -> SoftwareToken:
    key, cert = make_cert("AC de Prueba", ca=True, cuil=None)
    return SoftwareToken(cert_id, cert.public_bytes(serialization.Encoding.DER), key)
