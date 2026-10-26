"""Token de software para demostraciones: un certificado con su clave privada leídos de un archivo PEM.

No reemplaza al token físico: la clave vive en un archivo sin cifrar. Se usa con `firmadoc-agent run
--software-token RUTA` para recorrer la firma con token sin hardware (modo demostración de Firmadoc).
"""

from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from .testing import SoftwareBackend, SoftwareToken

SOFTWARE_PIN = "1234"
LABEL = "Token de software (demostración)"


class SoftwareTokenError(Exception):
    """El archivo no sirve como token de software (mensaje listo para mostrar)."""


def load_software_token(path: Path) -> SoftwareToken:
    try:
        pem = path.read_bytes()
    except OSError as e:
        raise SoftwareTokenError(f"no se pudo leer {path}: {e}") from e
    if b"-----BEGIN CERTIFICATE-----" not in pem:
        raise SoftwareTokenError(f"{path} no contiene un certificado (bloque CERTIFICATE)")
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except (ValueError, TypeError) as e:
        raise SoftwareTokenError(f"{path} no contiene una clave privada sin cifrar: {e}") from e
    if not isinstance(key, rsa.RSAPrivateKey):
        raise SoftwareTokenError("el token de software requiere una clave RSA")
    certificate = x509.load_pem_x509_certificate(pem[pem.find(b"-----BEGIN CERTIFICATE-----") :])
    if certificate.public_key().public_numbers() != key.public_key().public_numbers():
        raise SoftwareTokenError("la clave privada no corresponde al certificado")
    cert_id = f"SOFT:{certificate.serial_number:x}"[:40]
    return SoftwareToken(cert_id, certificate.public_bytes(serialization.Encoding.DER), key, LABEL)


def software_backend(path: Path, pin: str = SOFTWARE_PIN) -> SoftwareBackend:
    return SoftwareBackend([load_software_token(path)], pin=pin)
