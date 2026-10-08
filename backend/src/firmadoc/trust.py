"""Anclas de confianza cargadas desde disco (`FIRMADOC_TRUST_DIR`)."""

import hashlib
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from asn1crypto import pem
from asn1crypto import x509 as ax509

CERT_SUFFIXES = {".crt", ".pem", ".cer"}


@dataclass(frozen=True)
class TrustedCert:
    cert: ax509.Certificate
    fingerprint: str  # SHA-256 en hexadecimal
    subject: str
    is_root: bool


@dataclass(frozen=True)
class TrustStore:
    certs: tuple[TrustedCert, ...]

    @property
    def roots(self) -> list[ax509.Certificate]:
        return [c.cert for c in self.certs if c.is_root]

    @property
    def intermediates(self) -> list[ax509.Certificate]:
        return [c.cert for c in self.certs if not c.is_root]


def _load_file(path: Path) -> list[ax509.Certificate]:
    data = path.read_bytes()
    if pem.detect(data):
        return [ax509.Certificate.load(der) for _t, _h, der in pem.unarmor(data, multiple=True)]
    return [ax509.Certificate.load(data)]


def _read_directory(directory: Path) -> TrustStore:
    found: dict[str, TrustedCert] = {}
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() not in CERT_SUFFIXES:
                continue
            for cert in _load_file(path):
                fingerprint = hashlib.sha256(cert.dump()).hexdigest()
                found[fingerprint] = TrustedCert(
                    cert=cert,
                    fingerprint=fingerprint,
                    subject=cert.subject.human_friendly,
                    is_root=cert.subject == cert.issuer,
                )
    return TrustStore(tuple(found.values()))


@lru_cache
def _cached(directory: str) -> TrustStore:
    return _read_directory(Path(directory))


def load_trust_store(directory: str | Path) -> TrustStore:
    """Se carga una vez por proceso y directorio; reiniciar para tomar cambios."""
    return _cached(str(directory))


def main(argv: list[str] | None = None) -> int:
    from .config import get_settings

    args = argv if argv is not None else sys.argv[1:]
    if args != ["list"]:
        print("uso: python -m firmadoc.trust list")
        return 2
    store = _read_directory(Path(get_settings().trust_dir))
    if not store.certs:
        print("No hay anclas de confianza cargadas.")
        return 0
    for c in store.certs:
        print(f"{'RAIZ' if c.is_root else 'AC  '}  {c.fingerprint}  {c.subject}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
