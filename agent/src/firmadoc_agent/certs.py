"""Lectura de los datos públicos de un certificado X.509."""

from cryptography import x509
from cryptography.x509.oid import NameOID

from .backend import TokenCertificate


def is_ca(cert: x509.Certificate) -> bool:
    try:
        return bool(cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)
    except x509.ExtensionNotFound:
        return False


def subject_serial_number(cert: x509.Certificate) -> str | None:
    """Atributo `serialNumber` del sujeto, tal cual (ahí suele ir el CUIL)."""
    attrs = cert.subject.get_attributes_for_oid(NameOID.SERIAL_NUMBER)
    return str(attrs[0].value) if attrs else None


def key_usage_text(cert: x509.Certificate) -> str:
    try:
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
    except x509.ExtensionNotFound:
        return "(sin extensión)"
    names = {
        "digital_signature": ku.digital_signature,
        "non_repudiation": ku.content_commitment,
        "key_encipherment": ku.key_encipherment,
        "key_cert_sign": ku.key_cert_sign,
    }
    return ", ".join(n for n, on in names.items() if on) or "(ninguno)"


def to_token_certificate(cert_id: str, token_label: str, der: bytes) -> TokenCertificate | None:
    """`None` si es un certificado de AC (no se ofrece para firmar)."""
    if is_ca(x509.load_der_x509_certificate(der)):
        return None
    return describe_certificate(cert_id, token_label, der)


def describe_certificate(cert_id: str, token_label: str, der: bytes) -> TokenCertificate:
    cert = x509.load_der_x509_certificate(der)
    return TokenCertificate(
        id=cert_id,
        token_label=token_label,
        subject=cert.subject.rfc4514_string(),
        issuer=cert.issuer.rfc4514_string(),
        serial_number=str(cert.serial_number),
        not_before=cert.not_valid_before_utc,
        not_after=cert.not_valid_after_utc,
        der=der,
    )
