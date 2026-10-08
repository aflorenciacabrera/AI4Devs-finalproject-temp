"""Proveedor `local`: certificado autofirmado de demostración (firma electrónica, no digital)."""

import datetime
import os
import threading
from pathlib import Path

from asn1crypto import x509 as ax509
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from cryptography.x509.oid import NameOID
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Certificate, Provider, RevocationStatus, Signer
from ..pdf_engine import verify_last_signature
from .base import ResolvedCertificate

KEY_FILE = "demo-signer.key"
CERT_FILE = "demo-signer.crt"
SUBJECT_CN = "Firmadoc Demo Signer (firma electronica de demostracion)"
_lock = threading.Lock()


class LocalPAdESProvider:
    provider = Provider.LOCAL

    def __init__(self, cert_dir: str | Path):
        self._dir = Path(cert_dir)
        self._key: rsa.RSAPrivateKey | None = None
        self._cert: x509.Certificate | None = None

    def _load(self) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
        if self._key is not None and self._cert is not None:
            return self._key, self._cert
        with _lock:
            key_path, cert_path = self._dir / KEY_FILE, self._dir / CERT_FILE
            if not (key_path.exists() and cert_path.exists()):
                self._generate(key_path, cert_path)
            self._key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
            self._cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
            return self._key, self._cert

    def _generate(self, key_path: Path, cert_path: Path) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, SUBJECT_CN),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Firmadoc"),
            ]
        )
        now = datetime.datetime.now(datetime.UTC)
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=365 * 5))
            .add_extension(
                x509.KeyUsage(True, True, False, False, False, False, False, False, False),
                critical=True,
            )
            .sign(key, hashes.SHA256())
        )
        pem_key = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        # La clave se crea ya con permisos restringidos (best effort en Windows).
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(pem_key)
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    def resolve_certificate(
        self, db: Session, certificate_pem: str | None, signer: Signer
    ) -> ResolvedCertificate:
        _key, cert = self._load()  # `certificate_pem` y `signer` se ignoran: firma el servidor
        serial = str(cert.serial_number)
        record = db.scalar(select(Certificate).where(Certificate.serial_number == serial))
        if record is None:
            record = Certificate(
                subject=cert.subject.rfc4514_string(),
                issuer_subject=cert.issuer.rfc4514_string(),
                serial_number=serial,
                provider=Provider.LOCAL,
                revocation_status=RevocationStatus.UNKNOWN,
                issued_at=cert.not_valid_before_utc,
                expires_at=cert.not_valid_after_utc,
            )
            db.add(record)
            db.flush()
        return ResolvedCertificate(record, cert.public_bytes(serialization.Encoding.DER))

    def revalidate_certificate(self, cert_der: bytes, signer: Signer) -> None:
        return None  # certificado propio: no hay terceros que validar

    def verify_result(self, pdf: bytes, cert_der: bytes) -> bool:
        return verify_last_signature(pdf, [ax509.Certificate.load(cert_der)], [])

    def obtain_signature(self, hash_to_sign: bytes, supplied: bytes | None) -> bytes:
        if supplied is not None:
            return supplied
        key, _cert = self._load()
        return key.sign(hash_to_sign, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256()))
