"""Motor PAdES sobre pyHanko: firma interrumpida en dos pasos (prepare / finish).

El PDF nunca se firma de una vez: `prepare_pdf` reserva el espacio de firma y devuelve el hash que
debe firmar quien tenga la clave; `finish_pdf` incrusta la firma recibida.
"""

import asyncio
import base64
import hashlib
import io
from dataclasses import dataclass

from asn1crypto import cms
from asn1crypto import x509 as ax509
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, utils
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import signers
from pyhanko.sign.fields import SigSeedSubFilter
from pyhanko.sign.signers.pdf_byterange import PreparedByteRangeDigest
from pyhanko.sign.signers.pdf_signer import PdfSignatureMetadata, PdfSigner, PdfTBSDocument
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext
from pyhanko_certvalidator.registry import SimpleCertificateStore

RESERVED_BYTES = 16 * 1024
MD_ALGORITHM = "sha256"


class PdfEngineError(Exception):
    pass


class TimestampUnavailable(Exception):
    """La TSA no respondió, devolvió un error o un sello inválido."""


@dataclass(frozen=True)
class PreparedPdf:
    hash_to_sign: bytes
    pdf: bytes  # PDF con el espacio de firma reservado (no es un documento válido todavía)
    state: dict  # JSON-serializable: digest, región reservada y atributos firmados


def validate_pdf(data: bytes) -> None:
    if not data.startswith(b"%PDF-"):
        raise PdfEngineError("el archivo no es un PDF")
    try:
        PdfFileReader(io.BytesIO(data))
    except Exception as e:
        raise PdfEngineError("el PDF no se pudo leer") from e


def signature_count(pdf: bytes) -> int:
    return len(PdfFileReader(io.BytesIO(pdf)).embedded_signatures)


def _registry(cert: ax509.Certificate) -> SimpleCertificateStore:
    registry = SimpleCertificateStore()
    registry.register(cert)
    return registry


def prepare_pdf(pdf: bytes, cert: ax509.Certificate, reason: str) -> PreparedPdf:
    return asyncio.run(_prepare(pdf, cert, reason))


async def _prepare(pdf: bytes, cert: ax509.Certificate, reason: str) -> PreparedPdf:
    signer = signers.ExternalSigner(
        signing_cert=cert, cert_registry=_registry(cert), signature_value=bytes(256)
    )
    meta = PdfSignatureMetadata(
        field_name=f"Firmadoc-{signature_count(pdf) + 1}",
        md_algorithm=MD_ALGORITHM,
        subfilter=SigSeedSubFilter.PADES,
        reason=reason,
    )
    writer = IncrementalPdfFileWriter(io.BytesIO(pdf))
    prepared, _tbs, output = await PdfSigner(meta, signer=signer).async_digest_doc_for_signing(
        writer, bytes_reserved=RESERVED_BYTES
    )
    attrs = await signer.signed_attrs(prepared.document_digest, MD_ALGORITHM, use_pades=True)
    attrs_der = attrs.dump()
    state = {
        "digest": base64.b64encode(prepared.document_digest).decode(),
        "start": prepared.reserved_region_start,
        "end": prepared.reserved_region_end,
        "attrs": base64.b64encode(attrs_der).decode(),
    }
    return PreparedPdf(hashlib.sha256(attrs_der).digest(), output.getvalue(), state)


def finish_pdf(
    prepared_pdf: bytes,
    state: dict,
    cert: ax509.Certificate,
    signature: bytes,
    timestamper=None,
) -> bytes:
    return asyncio.run(_finish(prepared_pdf, state, cert, signature, timestamper))


async def _finish(
    prepared_pdf: bytes,
    state: dict,
    cert: ax509.Certificate,
    signature: bytes,
    timestamper=None,
) -> bytes:
    signer = signers.ExternalSigner(
        signing_cert=cert, cert_registry=_registry(cert), signature_value=signature
    )
    attrs = cms.CMSAttributes.load(base64.b64decode(state["attrs"]))
    if timestamper is None:
        signature_cms = await signer.async_sign_prescribed_attributes(MD_ALGORITHM, signed_attrs=attrs)
    else:
        try:  # solo el pedido del sello: un PDF defectuoso no debe confundirse con una TSA caída
            signature_cms = await signer.async_sign_prescribed_attributes(
                MD_ALGORITHM, signed_attrs=attrs, timestamper=timestamper
            )
        except Exception as e:
            raise TimestampUnavailable(f"{type(e).__name__}: {e}") from e
    prepared = PreparedByteRangeDigest(
        base64.b64decode(state["digest"]), state["start"], state["end"]
    )
    out = io.BytesIO(prepared_pdf)
    await PdfTBSDocument.async_finish_signing(out, prepared, signature_cms)
    return out.getvalue()


def verify_hash_signature(cert_der: bytes, hash_to_sign: bytes, signature: bytes) -> bool:
    """¿`signature` es una firma RSA PKCS#1 v1.5 válida de `hash_to_sign` con la clave del certificado?"""
    public_key = x509.load_der_x509_certificate(cert_der).public_key()
    try:
        public_key.verify(
            signature, hash_to_sign, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256())
        )
    except (InvalidSignature, TypeError, AttributeError):
        return False
    return True


@dataclass(frozen=True)
class SignatureCheck:
    field_name: str
    signer_subject: str
    serial_number: str
    claimed_signing_time: str | None
    intact: bool
    valid: bool
    trusted: bool
    modification_level: str
    ok: bool  # íntegra, válida, de confianza, sin modificaciones no permitidas y con sello confiable (si lo tiene)
    timestamp_present: bool = False
    timestamp_time: str | None = None
    timestamp_intact: bool = False
    timestamp_valid: bool = False
    timestamp_trusted: bool = False


_ALLOWED_MODIFICATIONS = {"NONE", "LTA_UPDATES", "FORM_FILLING"}  # firmas posteriores, sellos y campos


def verify_pdf(
    pdf: bytes, trust_roots: list[ax509.Certificate], other_certs: list[ax509.Certificate]
) -> list[SignatureCheck]:
    """Valida todas las firmas incrustadas, sin consultar revocación ni la red."""
    context = ValidationContext(
        trust_roots=trust_roots, other_certs=other_certs, allow_fetching=False
    )
    checks = []
    for sig in PdfFileReader(io.BytesIO(pdf)).embedded_signatures:
        status = validate_pdf_signature(sig, context)
        level = status.modification_level.name if status.modification_level else "NONE"
        cert = sig.signer_cert
        reported = status.signer_reported_dt
        stamp = status.timestamp_validity
        stamp_ok = stamp is None or bool(stamp.intact and stamp.valid and stamp.trusted)
        checks.append(
            SignatureCheck(
                field_name=sig.field_name,
                signer_subject=cert.subject.human_friendly,
                serial_number=str(cert.serial_number),
                claimed_signing_time=reported.isoformat() if reported else None,
                intact=bool(status.intact),
                valid=bool(status.valid),
                trusted=bool(status.trusted),
                modification_level=level,
                ok=bool(
                    status.intact
                    and status.valid
                    and status.trusted
                    and level in _ALLOWED_MODIFICATIONS
                    and stamp_ok
                ),
                timestamp_present=stamp is not None,
                timestamp_time=stamp.timestamp.isoformat() if stamp is not None else None,
                timestamp_intact=bool(stamp.intact) if stamp is not None else False,
                timestamp_valid=bool(stamp.valid) if stamp is not None else False,
                timestamp_trusted=bool(stamp.trusted) if stamp is not None else False,
            )
        )
    return checks


def verify_last_signature(
    pdf: bytes, trust_roots: list[ax509.Certificate], other_certs: list[ax509.Certificate]
) -> bool:
    """¿La última firma del PDF es íntegra, válida y llega a un ancla de confianza?"""
    signatures = PdfFileReader(io.BytesIO(pdf)).embedded_signatures
    if not signatures:
        return False
    context = ValidationContext(
        trust_roots=trust_roots, other_certs=other_certs, allow_fetching=False
    )
    status = validate_pdf_signature(signatures[-1], context)
    return bool(status.intact and status.valid and status.trusted)
