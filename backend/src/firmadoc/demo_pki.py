"""PKI de prueba del modo demostración (sin valor legal): una AC y un firmante con CUIL.

Sirve para recorrer la firma con token sin hardware: el agente carga `firmante.pem` como «token de software»
y el servidor confía en `ca.crt`. La clave privada queda sin cifrar en `data/demo/` (ignorado por git).
"""

import datetime
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

DAY = datetime.timedelta(days=1)
CA_FILE = "ca.crt"
SIGNER_FILE = "firmante.pem"
DEMO_SIGNER_NAME = "Firmante de Prueba"
DEMO_SIGNER_CUIL = "20000000001"
DEMO_SIGNER_EMAIL = "demo@example.org"
DEMO_PIN = "1234"  # el PIN que acepta el agente con token de software


@dataclass(frozen=True)
class DemoPki:
    directory: Path
    ca: x509.Certificate
    signer: x509.Certificate

    @property
    def ca_path(self) -> Path:
        return self.directory / CA_FILE

    @property
    def signer_path(self) -> Path:
        return self.directory / SIGNER_FILE


def _name(cn: str, cuil: str | None = None) -> x509.Name:
    attrs = [x509.NameAttribute(NameOID.COUNTRY_NAME, "AR"), x509.NameAttribute(NameOID.COMMON_NAME, cn)]
    if cuil:
        attrs.append(x509.NameAttribute(NameOID.SERIAL_NUMBER, f"CUIL {cuil}"))
    return x509.Name(attrs)


def _generate(directory: Path) -> None:
    now = datetime.datetime.now(datetime.UTC)
    ca_key = rsa.generate_private_key(65537, 2048)
    ca_name = _name("AC de Prueba Firmadoc (sin valor legal)")
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - DAY)
        .not_valid_after(now + 3650 * DAY)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    key = rsa.generate_private_key(65537, 2048)
    signer = (
        x509.CertificateBuilder()
        .subject_name(_name(DEMO_SIGNER_NAME, DEMO_SIGNER_CUIL))
        .issuer_name(ca_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - DAY)
        .not_valid_after(now + 3650 * DAY)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(True, True, False, False, False, False, False, False, False), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / CA_FILE).write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (directory / SIGNER_FILE).write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),  # solo demostración
        )
        + signer.public_bytes(serialization.Encoding.PEM)
    )
    # la clave de la AC se descarta: no hace falta emitir más certificados


def ensure_demo_pki(directory: Path) -> DemoPki:
    """Crea la PKI de prueba la primera vez y la reutiliza después (misma AC, mismo certificado)."""
    ca_path, signer_path = directory / CA_FILE, directory / SIGNER_FILE
    if not (ca_path.is_file() and signer_path.is_file()):
        _generate(directory)
    ca = x509.load_pem_x509_certificate(ca_path.read_bytes())
    signer = x509.load_pem_x509_certificate(_certificate_block(signer_path.read_bytes()))
    return DemoPki(directory=directory, ca=ca, signer=signer)


def _certificate_block(pem: bytes) -> bytes:
    start = pem.find(b"-----BEGIN CERTIFICATE-----")
    if start < 0:
        raise ValueError(f"{SIGNER_FILE} no contiene un certificado")
    return pem[start:]


def ensure_trust_dir(trust_dir: Path, repo_trust_dir: Path, pki: DemoPki) -> Path:
    """Directorio de confianza de la demo: las anclas del repositorio más la AC de prueba. No toca el del repo."""
    trust_dir.mkdir(parents=True, exist_ok=True)
    if repo_trust_dir.is_dir():
        for path in repo_trust_dir.iterdir():
            if path.suffix.lower() in {".crt", ".pem", ".cer"} and path.is_file():
                (trust_dir / path.name).write_bytes(path.read_bytes())
    (trust_dir / "demo-ca.crt").write_bytes(pki.ca.public_bytes(serialization.Encoding.PEM))
    return trust_dir
