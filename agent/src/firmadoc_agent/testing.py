"""Dobles para probar el agente sin hardware ni ventanas (también los usan los tests del servidor)."""

from dataclasses import dataclass, field

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa

from . import errors
from .backend import TokenCertificate, TokenInfo, digest_info
from .certs import describe_certificate, is_ca, to_token_certificate
from .ui import SignPrompt


@dataclass
class SoftwareToken:
    """Un certificado con su clave privada, como si estuviera en el token."""

    cert_id: str
    der: bytes
    key: rsa.RSAPrivateKey
    label: str = "Token de prueba"


class SoftwareBackend:
    """Implementa el contrato igual que `CKM_RSA_PKCS`: relleno PKCS#1 v1.5 sobre el DigestInfo."""

    def __init__(self, tokens: list[SoftwareToken], pin: str = "1234", retries: int = 3):
        self.tokens = tokens
        self.pin = pin
        self.retries_left = retries
        self.login_attempts = 0
        self.sign_calls = 0
        self.open_sessions = 0
        self.fail_at_index: int | None = None

    def list_certificates(self) -> list[TokenCertificate]:
        if not self.tokens:
            raise errors.token_not_found()
        out = [to_token_certificate(t.cert_id, t.label, t.der) for t in self.tokens]
        return [c for c in out if c is not None]

    def inspect(self) -> list[TokenInfo]:
        if not self.tokens:
            return []
        certs = [
            (describe_certificate(t.cert_id, t.label, t.der), is_ca(x509.load_der_x509_certificate(t.der)))
            for t in self.tokens
        ]
        flags = ["inicializado"] + (["último intento de PIN"] if self.retries_left == 1 else [])
        return [TokenInfo(self.tokens[0].label, "Prueba", "SoftwareToken", "SOFT-0001", flags, certs)]

    def final_try(self, certificate_id: str) -> bool:
        return self.retries_left == 1

    def sign(self, certificate_id: str, pin: str, digests: list[bytes]) -> list[bytes]:
        token = next((t for t in self.tokens if t.cert_id == certificate_id), None)
        if token is None:
            raise errors.certificate_not_found()
        self.open_sessions += 1
        try:
            self.login_attempts += 1
            if self.retries_left == 0:
                raise errors.pin_locked()
            if pin != self.pin:
                self.retries_left -= 1
                if self.retries_left == 0:
                    raise errors.pin_locked()
                raise errors.pin_incorrect()
            self.retries_left = 3
            signatures = []
            for i, digest in enumerate(digests):
                if self.fail_at_index == i:
                    raise errors.AgentError("pkcs11_error", "falló la firma", 500)
                signatures.append(self._raw_rsa_pkcs(token, digest_info(digest)))
                self.sign_calls += 1
            return signatures
        finally:
            self.open_sessions -= 1  # logout + cierre de sesión

    @staticmethod
    def _raw_rsa_pkcs(token: SoftwareToken, data: bytes) -> bytes:
        numbers = token.key.private_numbers()
        n = numbers.public_numbers.n
        size = (n.bit_length() + 7) // 8
        padded = b"\x00\x01" + b"\xff" * (size - len(data) - 3) + b"\x00" + data
        return pow(int.from_bytes(padded, "big"), numbers.d, n).to_bytes(size, "big")

    @staticmethod
    def public_key(token: SoftwareToken):
        return x509.load_der_x509_certificate(token.der).public_key()


@dataclass
class FakeUI:
    """Responde con un PIN fijo, cancela o simula el tiempo agotado."""

    pin: str | None = "1234"
    prompts: list[SignPrompt] = field(default_factory=list)
    before_answer: object = None  # callable opcional: se ejecuta mientras el "diálogo" está abierto

    def ask_pin(self, prompt: SignPrompt) -> str | None:
        self.prompts.append(prompt)
        if callable(self.before_answer):
            self.before_answer()
        return self.pin
