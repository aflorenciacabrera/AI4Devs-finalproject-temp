"""PKI de prueba (sin valor legal): raíz, AC intermedia y firmantes con CUIL."""

import base64
import datetime
from dataclasses import dataclass

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

DAY = datetime.timedelta(days=1)

# Prefijo ASN.1 de DigestInfo para SHA-256 (RFC 8017, sección 9.2).
SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _name(cn: str, cuil: str | None = None) -> x509.Name:
    attrs = [
        x509.NameAttribute(NameOID.COUNTRY_NAME, "AR"),
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
    ]
    if cuil:
        attrs.append(x509.NameAttribute(NameOID.SERIAL_NUMBER, f"CUIL {cuil}"))
    return x509.Name(attrs)


@dataclass
class Identity:
    key: rsa.RSAPrivateKey
    cert: x509.Certificate

    @property
    def der(self) -> bytes:
        return self.cert.public_bytes(serialization.Encoding.DER)

    @property
    def pem(self) -> str:
        return self.cert.public_bytes(serialization.Encoding.PEM).decode()


class Authority:
    def __init__(self, cn: str, parent: "Authority | None" = None, key_size: int = 2048):
        self.key = rsa.generate_private_key(65537, key_size)
        self.parent = parent
        issuer_key = parent.key if parent else self.key
        issuer_name = parent.cert.subject if parent else _name(cn)
        now = _now()
        self.cert = (
            x509.CertificateBuilder()
            .subject_name(_name(cn))
            .issuer_name(issuer_name)
            .public_key(self.key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - 30 * DAY)
            .not_valid_after(now + 3650 * DAY)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(False, False, False, False, False, True, True, False, False),
                critical=True,
            )
            .sign(issuer_key, hashes.SHA256())
        )
        self.revoked: list[x509.Certificate] = []

    @property
    def pem(self) -> bytes:
        return self.cert.public_bytes(serialization.Encoding.PEM)

    @property
    def der(self) -> bytes:
        return self.cert.public_bytes(serialization.Encoding.DER)

    def issue(
        self,
        cn: str,
        cuil: str | None = "20111111112",
        *,
        not_before: datetime.datetime | None = None,
        not_after: datetime.datetime | None = None,
        key_size: int = 2048,
        digital_signature: bool = True,
    ) -> Identity:
        key = rsa.generate_private_key(65537, key_size)
        now = _now()
        builder = (
            x509.CertificateBuilder()
            .subject_name(_name(cn, cuil))
            .issuer_name(self.cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(not_before or now - 30 * DAY)
            .not_valid_after(not_after or now + 365 * DAY)
            .add_extension(
                x509.KeyUsage(
                    digital_signature, digital_signature, False, False, False, False, False,
                    False, False,
                ),
                critical=True,
            )
            .add_extension(
                x509.CRLDistributionPoints(
                    [
                        x509.DistributionPoint(
                            [x509.UniformResourceIdentifier("http://crl.invalid/ca.crl")],
                            None, None, None,
                        )
                    ]
                ),
                critical=False,
            )
        )
        return Identity(key, builder.sign(self.key, hashes.SHA256()))

    def revoke(self, identity: Identity) -> None:
        self.revoked.append(identity.cert)

    def crl(self) -> bytes:
        now = _now()
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(self.cert.subject)
            .last_update(now - DAY)
            .next_update(now + 30 * DAY)
        )
        for cert in self.revoked:
            builder = builder.add_revoked_certificate(
                x509.RevokedCertificateBuilder()
                .serial_number(cert.serial_number)
                .revocation_date(now - DAY)
                .build()
            )
        return builder.sign(self.key, hashes.SHA256()).public_bytes(serialization.Encoding.DER)


class Pki:
    """Raíz → AC intermedia → firmantes; más una AC ajena para los casos de rechazo."""

    def __init__(self):
        self.root = Authority("Raiz de Prueba")
        self.ca = Authority("AC de Prueba", parent=self.root)
        self.other_root = Authority("Otra Raiz de Prueba")
        self.other_ca = Authority("Otra AC de Prueba", parent=self.other_root)

    def write_anchors(self, directory) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "raiz.crt").write_bytes(self.root.pem)
        (directory / "ac.crt").write_bytes(self.ca.pem)

    def write_crls(self, directory) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "ac.crl").write_bytes(self.ca.crl())


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()
