"""Autoprueba para validar un token (físico o de prueba): firma un lote y verifica con la clave pública.

Es el procedimiento de la prueba manual con un token real: hace UN solo login (un único ingreso de
PIN para todo el lote) y comprueba que el token acepta `CKM_RSA_PKCS` con el DigestInfo del contrato.
"""

import hashlib
from collections.abc import Callable

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, utils

from .backend import TokenBackend


def self_test(
    backend: TokenBackend,
    pin: str,
    certificate_id: str | None = None,
    batch: int = 3,
    out: Callable[[str], None] = print,
) -> bool:
    certs = backend.list_certificates()
    if not certs:
        out("FALLO: el token no tiene certificados de usuario.")
        return False
    cert = next((c for c in certs if c.id == certificate_id), None) if certificate_id else certs[0]
    if cert is None:
        out(f"FALLO: no existe el certificado {certificate_id}. Disponibles: {[c.id for c in certs]}")
        return False
    out(f"Certificado: {cert.subject}  (id: {cert.id})")

    digests = [hashlib.sha256(f"documento-de-prueba-{i}".encode()).digest() for i in range(batch)]
    out(f"Firmando un lote de {batch} hashes con un único login...")
    signatures = backend.sign(cert.id, pin, digests)
    if len(signatures) != batch:
        out(f"FALLO: se pidieron {batch} firmas y llegaron {len(signatures)}.")
        return False

    public_key = x509.load_der_x509_certificate(cert.der).public_key()
    ok = True
    for i, (digest, signature) in enumerate(zip(digests, signatures, strict=True), start=1):
        try:
            public_key.verify(
                signature, digest, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256())
            )
            out(f"  [{i}] OK: RSA PKCS#1 v1.5 sobre DigestInfo SHA-256, {len(signature)} bytes")
        except Exception as e:  # noqa: BLE001 - se informa y se sigue con el resto
            out(f"  [{i}] FALLO: la firma no verifica con la clave pública del certificado ({e!r})")
            ok = False
    out("RESULTADO: CORRECTO" if ok else "RESULTADO: FALLÓ")
    return ok
