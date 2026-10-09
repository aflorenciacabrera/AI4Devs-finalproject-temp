"""Validación de certificados de firmantes (proveedor `token`).

Orden de las comprobaciones: formato y clave → vigencia → uso de clave → cadena y revocación →
CUIL. El CUIL va al final para no revelar datos de identidad a quien presenta un certificado que ni
siquiera es confiable.
"""

import asyncio
import hashlib
import logging
import re
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from asn1crypto import crl as acrl
from asn1crypto import x509 as ax509
from cryptography import x509
from pyhanko_certvalidator import CertificateValidator, ValidationContext, errors

from .errors import Forbidden, Unprocessable
from .models import RevocationStatus
from .trust import TrustStore

log = logging.getLogger("firmadoc.certificate_validation")

MIN_RSA_BITS = 2048
CUIL_RE = re.compile(r"CUIL\s*(\d{11})", re.IGNORECASE)

# Fallos de revocación "indeterminados" (no es que esté revocado: no se pudo saber).
_INDETERMINATE = (
    errors.InsufficientRevinfoError,
    errors.CRLFetchError,
    errors.OCSPFetchError,
    errors.CRLNoMatchesError,
    errors.OCSPNoMatchesError,
    errors.CRLValidationIndeterminateError,
    errors.OCSPValidationIndeterminateError,
    errors.StaleRevinfoError,
)


@dataclass(frozen=True)
class ValidatedCertificate:
    der: bytes
    subject: str
    issuer_subject: str
    serial_number: str
    cuil: str | None
    not_before: datetime
    not_after: datetime
    revocation_status: RevocationStatus


def invalid(detail: str) -> Unprocessable:
    return Unprocessable(detail, code="certificate_invalid")


def extract_cuil(cert: ax509.Certificate) -> str | None:
    """CUIL del `serialNumber` del sujeto (formato "CUIL 20123456789"). Aislado para ajustarlo."""
    serial = cert.subject.native.get("serial_number")
    match = CUIL_RE.search(serial) if isinstance(serial, str) else None
    return match.group(1) if match else None


def normalize_cuil(value: str) -> str:
    return re.sub(r"\D", "", value)


def load_crls(crl_dir: str | None) -> list[bytes]:
    if not crl_dir or not Path(crl_dir).is_dir():
        return []
    return [p.read_bytes() for p in sorted(Path(crl_dir).iterdir()) if p.suffix in {".crl", ".der"}]


class CrlCache:
    """CRL obtenidas por red, compartidas por todo el proceso mientras estén vigentes.

    Una CRL real de firmantes puede pesar varios MB: sin esto, cada `prepare`, cada `complete` y cada
    documento de un lote la descargaban de nuevo. Se guarda una copia por huella (dos puntos de
    distribución entregan la misma lista) y se purgan las vencidas por `next_update`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._crls: dict[str, acrl.CertificateList] = {}

    @staticmethod
    def _parse(item: bytes | acrl.CertificateList) -> acrl.CertificateList:
        return item if isinstance(item, acrl.CertificateList) else acrl.CertificateList.load(item)

    @staticmethod
    def _next_update(crl: acrl.CertificateList) -> datetime | None:
        value = crl["tbs_cert_list"]["next_update"]
        return value.native if value is not None and value.native is not None else None

    def add(self, crls: Iterable[bytes | acrl.CertificateList]) -> int:
        """Incorpora las CRL nuevas (ignora repetidas). Devuelve cuántas se agregaron."""
        added = 0
        with self._lock:
            for item in crls:
                crl = self._parse(item)
                key = hashlib.sha256(crl.dump()).hexdigest()
                if key in self._crls:
                    continue
                self._crls[key] = crl
                added += 1
                issuer = crl["tbs_cert_list"]["issuer"].native.get("common_name", "?")
                log.info(
                    "CRL incorporada a la caché: emisor=%s next_update=%s bytes=%d",
                    issuer, self._next_update(crl), len(crl.dump()),
                )
        return added

    def fresh(self, now: datetime) -> list[acrl.CertificateList]:
        """CRL vigentes en `now`; las vencidas se eliminan."""
        with self._lock:
            expired = [k for k, c in self._crls.items() if (nu := self._next_update(c)) and nu <= now]
            for key in expired:
                del self._crls[key]
            return list(self._crls.values())

    def clear(self) -> None:
        with self._lock:
            self._crls.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._crls)


CRL_CACHE = CrlCache()


class CertificateChecker:
    def __init__(
        self,
        trust: TrustStore,
        revocation_mode: str = "soft-fail",
        *,
        allow_fetching: bool = True,
        crls: list[bytes | acrl.CertificateList] | None = None,
        crl_cache: CrlCache | None = None,
    ):
        if revocation_mode not in {"hard-fail", "soft-fail", "off"}:
            raise ValueError(f"modo de revocación desconocido: {revocation_mode}")
        self.trust = trust
        self.revocation_mode = revocation_mode
        self.allow_fetching = allow_fetching and revocation_mode != "off"
        self.crls = list(crls or [])  # CRL locales (FIRMADOC_CRL_DIR): siempre se aplican
        self.crl_cache = CRL_CACHE if crl_cache is None else crl_cache

    # -- API pública -----------------------------------------------------------------------

    def validate(
        self, cert_der: bytes, expected_cuil: str | None = None, *, now: datetime | None = None
    ) -> ValidatedCertificate:
        now = now or datetime.now(UTC)
        try:
            cert = ax509.Certificate.load(cert_der)
            parsed = x509.load_der_x509_certificate(cert_der)
        except Exception as e:
            raise invalid("el certificado no se pudo leer") from e

        self._check_key(cert)
        self._check_validity(parsed, now)
        self._check_key_usage(cert)
        status = self._check_chain(cert, now)
        cuil = extract_cuil(cert)
        if expected_cuil is not None:
            self._check_cuil(cuil, expected_cuil)
        return ValidatedCertificate(
            der=cert_der,
            subject=parsed.subject.rfc4514_string(),
            issuer_subject=parsed.issuer.rfc4514_string(),
            serial_number=str(parsed.serial_number),
            cuil=cuil,
            not_before=parsed.not_valid_before_utc,
            not_after=parsed.not_valid_after_utc,
            revocation_status=status,
        )

    # -- comprobaciones ----------------------------------------------------------------------

    @staticmethod
    def _check_key(cert: ax509.Certificate) -> None:
        key = cert.public_key
        if key.algorithm != "rsa":
            raise invalid(f"algoritmo de clave no soportado: {key.algorithm}")
        if key.bit_size < MIN_RSA_BITS:
            raise invalid(f"clave RSA de {key.bit_size} bits: se exigen al menos {MIN_RSA_BITS}")

    @staticmethod
    def _check_validity(parsed: x509.Certificate, now: datetime) -> None:
        if now > parsed.not_valid_after_utc:
            raise Unprocessable("el certificado está vencido", code="certificate_expired")
        if now < parsed.not_valid_before_utc:
            raise invalid("el certificado todavía no es vigente")

    @staticmethod
    def _check_key_usage(cert: ax509.Certificate) -> None:
        usage = cert.key_usage_value
        if usage is None:
            return  # sin extensión: no restringe
        allowed = {"digital_signature", "non_repudiation", "content_commitment"}
        if not (set(usage.native) & allowed):
            raise invalid("el uso de clave del certificado no permite firmar")

    def _context(self, cert: ax509.Certificate, now: datetime, mode: str) -> ValidationContext:
        fetching = self.allow_fetching and mode != "off"
        return ValidationContext(
            trust_roots=self.trust.roots,
            other_certs=self.trust.intermediates,
            moment=now,
            allow_fetching=fetching,
            crls=None if mode == "off" else [*self.crls, *self.crl_cache.fresh(now)],
            revocation_mode="soft-fail" if mode == "off" else mode,
        )

    def _run(self, cert: ax509.Certificate, now: datetime, mode: str) -> None:
        context = self._context(cert, now, mode)
        validator = CertificateValidator(cert, validation_context=context)
        try:
            asyncio.run(validator.async_validate_usage(set()))
        finally:
            # Lo descargado sirve para las próximas validaciones, aun si esta falló.
            if self.allow_fetching and mode != "off":
                self.crl_cache.add(context.crls)

    def _check_chain(self, cert: ax509.Certificate, now: datetime) -> RevocationStatus:
        if self.revocation_mode == "off":
            self._chain_only(cert, now)
            return RevocationStatus.UNKNOWN
        try:
            self._run(cert, now, "hard-fail")
            return RevocationStatus.GOOD
        except errors.RevokedError as e:
            raise Unprocessable("el certificado está revocado", code="certificate_revoked") from e
        except _INDETERMINATE as e:
            if self.revocation_mode == "hard-fail":
                raise invalid("no se pudo verificar la revocación del certificado") from e
            self._chain_only(cert, now)  # soft-fail: la cadena debe ser válida igualmente
            return RevocationStatus.UNKNOWN
        except Exception as e:
            raise self._map(e) from e

    def _chain_only(self, cert: ax509.Certificate, now: datetime) -> None:
        try:
            self._run(cert, now, "off")
        except Exception as e:
            raise self._map(e) from e

    @staticmethod
    def _map(exc: Exception) -> Unprocessable:
        if isinstance(exc, errors.ExpiredError):
            return Unprocessable("el certificado o su cadena está vencida", code="certificate_expired")
        if isinstance(exc, errors.RevokedError):
            return Unprocessable("el certificado está revocado", code="certificate_revoked")
        if isinstance(exc, errors.PathBuildingError):
            return Unprocessable(
                "el certificado no pertenece a una cadena de confianza conocida",
                code="certificate_untrusted",
            )
        if isinstance(exc, errors.PathValidationError | errors.ValidationError):
            return Unprocessable(
                "la cadena del certificado no es válida", code="certificate_untrusted"
            )
        return invalid(f"no se pudo validar el certificado: {exc}")

    @staticmethod
    def _check_cuil(cuil: str | None, expected: str) -> None:
        if cuil is None:
            raise Forbidden("el certificado no contiene un CUIL", code="cuil_mismatch")
        if normalize_cuil(cuil) != normalize_cuil(expected):
            raise Forbidden("el CUIL del certificado no coincide con el del firmante", code="cuil_mismatch")
