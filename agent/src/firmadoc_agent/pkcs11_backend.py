"""Backend real: el token por PKCS#11 (python-pkcs11)."""

import hashlib
import logging

import pkcs11
from pkcs11 import Attribute, CertificateType, Mechanism, ObjectClass, TokenFlag
from pkcs11 import exceptions as p11

from . import errors
from .backend import TokenCertificate, TokenInfo, digest_info
from .certs import describe_certificate, is_ca, to_token_certificate
from .errors import AgentError

log = logging.getLogger("firmadoc_agent")


def _text(value) -> str:
    """python-pkcs11 devuelve algunos campos como bytes y otros como texto."""
    if isinstance(value, bytes | bytearray):
        value = bytes(value).decode("ascii", errors="replace")
    return (value or "").strip()


def _token_serial(token) -> str:
    return _text(token.serial) or _text(token.label)


class Pkcs11Backend:
    """Los identificadores de certificado tienen la forma `<serie del token>:<CKA_ID en hex>`."""

    def __init__(self, module_path: str | None):
        self._path = module_path
        self._lib = None

    # -- biblioteca y tokens ---------------------------------------------------------------

    def library(self):
        if not self._path:
            raise errors.pkcs11_unavailable(
                "no está configurado 'pkcs11_module' (ruta de la biblioteca PKCS#11 del fabricante)"
            )
        if self._lib is None:
            try:
                self._lib = pkcs11.lib(self._path)
            except Exception as e:
                raise errors.pkcs11_unavailable(
                    f"no se pudo cargar la biblioteca PKCS#11 '{self._path}': {e}. "
                    "Revise la ruta y que su arquitectura (32/64 bits) sea la del agente."
                ) from e
        return self._lib

    def tokens(self) -> list:
        try:
            tokens = [slot.get_token() for slot in self.library().get_slots(token_present=True)]
        except p11.PKCS11Error as e:
            raise errors.pkcs11_unavailable(f"error al consultar los slots: {e}") from e
        # SoftHSM (y algunos lectores) exponen un slot libre con un token sin inicializar
        return [t for t in tokens if t.flags & TokenFlag.TOKEN_INITIALIZED]

    def _find_token(self, serial: str):
        for token in self.tokens():
            if _token_serial(token) == serial:
                return token
        raise errors.token_not_found()

    @staticmethod
    def _split_id(certificate_id: str) -> tuple[str, bytes]:
        serial, _, cka = certificate_id.rpartition(":")
        try:
            return serial, bytes.fromhex(cka)
        except ValueError:
            raise errors.certificate_not_found() from None

    # -- TokenBackend ------------------------------------------------------------------------

    def list_certificates(self) -> list[TokenCertificate]:
        tokens = self.tokens()
        if not tokens:
            raise errors.token_not_found()
        found: list[TokenCertificate] = []
        for token in tokens:
            serial = _token_serial(token)
            try:
                with token.open() as session:  # sesión pública: sin PIN
                    objects = session.get_objects(
                        {
                            Attribute.CLASS: ObjectClass.CERTIFICATE,
                            Attribute.CERTIFICATE_TYPE: CertificateType.X_509,
                        }
                    )
                    for obj in objects:
                        cka = bytes(obj[Attribute.ID])
                        if not cka:
                            log.warning("certificado sin CKA_ID en %s: no se puede usar para firmar", serial)
                            continue
                        der = bytes(obj[Attribute.VALUE])
                        cert = to_token_certificate(f"{serial}:{cka.hex()}", _text(token.label), der)
                        if cert is not None:
                            found.append(cert)
            except p11.PKCS11Error as e:
                log.warning("no se pudieron leer los certificados de %s: %s", serial, e)
        return found

    def inspect(self) -> list[TokenInfo]:
        from cryptography import x509

        infos = []
        for token in self.tokens():
            serial = _token_serial(token)
            certs: list[tuple[TokenCertificate, bool]] = []
            with token.open() as session:  # sesión pública: nunca se pide PIN
                for obj in session.get_objects(
                    {
                        Attribute.CLASS: ObjectClass.CERTIFICATE,
                        Attribute.CERTIFICATE_TYPE: CertificateType.X_509,
                    }
                ):
                    der = bytes(obj[Attribute.VALUE])
                    cka = bytes(obj[Attribute.ID]).hex() or "(sin CKA_ID)"
                    certs.append(
                        (
                            describe_certificate(f"{serial}:{cka}", _text(token.label), der),
                            is_ca(x509.load_der_x509_certificate(der)),
                        )
                    )
            flags = [f.name.lower() for f in TokenFlag if token.flags & f]
            infos.append(
                TokenInfo(
                    _text(token.label), _text(token.manufacturer_id), _text(token.model), serial,
                    flags, certs,
                )
            )
        return infos

    def final_try(self, certificate_id: str) -> bool:
        serial, _ = self._split_id(certificate_id)
        try:
            return bool(self._find_token(serial).flags & TokenFlag.USER_PIN_FINAL_TRY)
        except p11.PKCS11Error:
            return False

    def sign(self, certificate_id: str, pin: str, digests: list[bytes]) -> list[bytes]:
        serial, cka = self._split_id(certificate_id)
        token = self._find_token(serial)
        try:
            # `open(user_pin=...)` hace exactamente un login; al salir del `with` se cierra la sesión
            # y con ella el login. No hay reintentos.
            with token.open(user_pin=pin) as session:
                key = session.get_key(object_class=ObjectClass.PRIVATE_KEY, id=cka)
                return [
                    bytes(key.sign(digest_info(d), mechanism=Mechanism.RSA_PKCS)) for d in digests
                ]
        except p11.PinLocked:
            raise errors.pin_locked() from None
        except p11.PinIncorrect:
            raise errors.pin_incorrect() from None
        except p11.PinExpired:
            raise AgentError(
                "pin_expired", "el PIN expiró: cámbielo con el software del fabricante", 401
            ) from None
        except p11.NoSuchKey:
            raise AgentError(
                "private_key_not_found", "la clave privada del certificado no está en el token", 404
            ) from None
        except (p11.TokenNotPresent, p11.NoSuchToken):
            raise errors.token_not_found() from None
        except p11.PKCS11Error as e:
            raise AgentError("pkcs11_error", f"error del token: {e}", 500) from e


def certificate_fingerprint(der: bytes) -> str:
    return hashlib.sha256(der).hexdigest()[:16]
