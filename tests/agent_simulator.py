"""Simulador del agente local: implementa el contrato de docs/agent-contract.md.

Hace lo que hará el agente real con `CKM_RSA_PKCS`: arma el `DigestInfo` SHA-256 del hash recibido,
aplica el relleno PKCS#1 v1.5 y exponencia con la clave privada (que en el token nunca sale).
"""

import base64

from .pki import SHA256_DIGEST_INFO, Identity


class AgentSimulator:
    def __init__(self, identity: Identity):
        self.identity = identity

    @property
    def certificate_pem(self) -> str:
        return self.identity.pem

    def sign(self, hash_to_sign_b64: str) -> str:
        digest = base64.b64decode(hash_to_sign_b64)
        if len(digest) != 32:
            raise ValueError("el contrato exige un hash SHA-256 de 32 bytes")
        numbers = self.identity.key.private_numbers()
        n = numbers.public_numbers.n
        size = (n.bit_length() + 7) // 8
        t = SHA256_DIGEST_INFO + digest
        padded = b"\x00\x01" + b"\xff" * (size - len(t) - 3) + b"\x00" + t
        signature = pow(int.from_bytes(padded, "big"), numbers.d, n).to_bytes(size, "big")
        return base64.b64encode(signature).decode()
