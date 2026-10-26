"""Servicio de firma remota SIMULADO (solo desarrollo y pruebas): replica el contrato de FirmAR/SIU.

Contrato: OAuth2 client credentials, envío de un documento, aprobación del usuario (OTP + PIN) y
callback con el PDF firmado y una firma HMAC del cuerpo. El estado vive en memoria: es un simulador.
Existe únicamente con `FIRMADOC_FIRMAR_MOCK_ENABLED=true`.
"""

import base64
import binascii
import datetime
import hmac
import html
import io
import json
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from asn1crypto import keys
from asn1crypto import x509 as ax509
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import APIRouter, Depends, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import signers
from pyhanko.sign.fields import SigSeedSubFilter
from pyhanko.sign.signers.pdf_signer import PdfSignatureMetadata
from pyhanko_certvalidator.registry import SimpleCertificateStore

from .api.deps import settings_dep
from .config import Settings
from .errors import NotFound
from .pdf_engine import signature_count, validate_pdf
from .providers import firmar

VALID_OTP = "123456"
VALID_PIN = "1234"
MAX_ATTEMPTS = 3
TOKEN_TTL = 300
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
CA_DIR = "firmar-mock"
_lock = threading.Lock()


@dataclass
class Operation:
    id: str
    pdf: bytes
    signer_cuil: str
    callback_url: str
    status: str = "pending"  # pending | signed | rejected | locked
    attempts: int = 0


_tokens: dict[str, float] = {}
_operations: dict[str, Operation] = {}


def reset() -> None:
    """Para las pruebas."""
    with _lock:
        _tokens.clear()
        _operations.clear()


def enabled(settings: Settings = Depends(settings_dep)) -> Settings:
    if not settings.firmar_mock_enabled:
        raise NotFound("no encontrado")
    return settings


def error(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "detail": detail})


def bearer(authorization: str | None = Header(default=None)) -> bool:
    scheme, _, token = (authorization or "").partition(" ")
    expires = _tokens.get(token.strip())
    return scheme.lower() == "bearer" and expires is not None and expires > time.time()


# --- autoridad y certificados del simulado ---------------------------------------------------------


def _name(cn: str, cuil: str | None = None) -> x509.Name:
    attrs = [x509.NameAttribute(NameOID.COMMON_NAME, cn)]
    if cuil:
        attrs.append(x509.NameAttribute(NameOID.SERIAL_NUMBER, f"CUIL {cuil}"))
    return x509.Name(attrs)


def ca_path(settings: Settings) -> Path:
    return Path(settings.local_cert_dir) / CA_DIR / "ca.crt"


def mock_ca_certificate(settings: Settings) -> ax509.Certificate | None:
    path = ca_path(settings)
    return ax509.Certificate.load(path.read_bytes()) if path.is_file() else None


def _load_ca(settings: Settings) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    directory = ca_path(settings).parent
    key_path, cert_path = directory / "ca.key", directory / "ca.crt.pem"
    with _lock:
        if not key_path.exists():
            directory.mkdir(parents=True, exist_ok=True)
            key = rsa.generate_private_key(65537, 2048)
            now = datetime.datetime.now(datetime.UTC)
            name = _name("AC del servicio FirmAR simulado")
            cert = (
                x509.CertificateBuilder()
                .subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - datetime.timedelta(minutes=5))
                .not_valid_after(now + datetime.timedelta(days=3650))
                .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                .add_extension(
                    x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True
                )
                .sign(key, hashes.SHA256())
            )
            key_path.write_bytes(
                key.private_bytes(
                    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
                )
            )
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            ca_path(settings).write_bytes(cert.public_bytes(serialization.Encoding.DER))
        return (
            serialization.load_pem_private_key(key_path.read_bytes(), password=None),
            x509.load_pem_x509_certificate(cert_path.read_bytes()),
        )


def _sign_pdf(settings: Settings, pdf: bytes, cuil: str) -> bytes:
    ca_key, ca_cert = _load_ca(settings)
    key = rsa.generate_private_key(65537, 2048)
    now = datetime.datetime.now(datetime.UTC)
    leaf = (
        x509.CertificateBuilder()
        .subject_name(_name("Firmante remoto (simulado)", cuil))
        .issuer_name(ca_cert.subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(
            x509.KeyUsage(True, True, False, False, False, False, False, False, False), critical=True
        )
        .sign(ca_key, hashes.SHA256())
    )
    registry = SimpleCertificateStore()
    registry.register(ax509.Certificate.load(ca_cert.public_bytes(serialization.Encoding.DER)))
    signer = signers.SimpleSigner(
        signing_cert=ax509.Certificate.load(leaf.public_bytes(serialization.Encoding.DER)),
        signing_key=keys.PrivateKeyInfo.load(
            key.private_bytes(
                serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        ),
        cert_registry=registry,
    )
    meta = PdfSignatureMetadata(
        field_name=f"FirmAR-{signature_count(pdf) + 1}",
        md_algorithm="sha256",
        subfilter=SigSeedSubFilter.PADES,
    )
    out = signers.sign_pdf(IncrementalPdfFileWriter(io.BytesIO(pdf)), meta, signer=signer)
    return out.getvalue()


def _call_back(settings: Settings, operation: Operation, status: str, signed: bytes | None) -> int:
    payload: dict = {"operation_id": operation.id, "status": status}
    if signed is not None:
        payload["signed_document_base64"] = base64.b64encode(signed).decode()
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = {
        "Content-Type": "application/json",
        firmar.SIGNATURE_HEADER: firmar.callback_signature(settings.firmar_callback_secret or "", body),
    }
    with httpx.Client(timeout=settings.firmar_timeout_seconds, transport=firmar.TRANSPORT) as client:
        return client.post(operation.callback_url, content=body, headers=headers).status_code


# --- rutas --------------------------------------------------------------------------------------------

router = APIRouter(prefix="/mock/firmar", dependencies=[Depends(enabled)], include_in_schema=False)


class OperationIn(BaseModel):
    document_base64: str | None = None
    documents: list[str] | None = None
    signer_cuil: str
    callback_url: str


class ApprovalIn(BaseModel):
    otp: str
    pin: str


@router.post("/oauth/token")
async def token(request: Request, settings: Settings = Depends(enabled)):
    form = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
    valid = (
        form.get("grant_type") == "client_credentials"
        and hmac.compare_digest(form.get("client_id", ""), settings.firmar_client_id)
        and bool(settings.firmar_client_secret)
        and hmac.compare_digest(form.get("client_secret", ""), settings.firmar_client_secret or "")
    )
    if not valid:
        return JSONResponse(status_code=401, content={"error": "invalid_client"})
    access_token = secrets.token_urlsafe(24)
    _tokens[access_token] = time.time() + TOKEN_TTL
    return {"access_token": access_token, "token_type": "Bearer", "expires_in": TOKEN_TTL}


@router.post("/v1/operations", status_code=201)
def create_operation(body: OperationIn, authorized: bool = Depends(bearer), settings: Settings = Depends(enabled)):
    if not authorized:
        return error(401, "invalid_token", "token ausente o vencido")
    documents = body.documents if body.documents is not None else ([body.document_base64] if body.document_base64 else [])
    if len(documents) != 1:
        return error(422, "documents_limit", "el simulado admite exactamente un documento por operación")
    try:
        pdf = base64.b64decode(documents[0], validate=True)
        validate_pdf(pdf)
    except (binascii.Error, ValueError, Exception):  # noqa: BLE001
        return error(422, "invalid_document", "el documento no es un PDF válido")
    if len(pdf) > MAX_DOCUMENT_BYTES:
        return error(422, "invalid_document", "el documento excede el tamaño máximo")
    operation = Operation(str(uuid.uuid4()), pdf, body.signer_cuil, body.callback_url)
    _operations[operation.id] = operation
    base = f"{settings.public_base_url.rstrip('/')}/mock/firmar"
    return {
        "operation_id": operation.id,
        "status": "pending",
        "authorization_url": f"{base}/authorize/{operation.id}",
    }


def _get(operation_id: str, authorized: bool) -> Operation | JSONResponse:
    if not authorized:
        return error(401, "invalid_token", "token ausente o vencido")
    operation = _operations.get(operation_id)
    return operation or error(404, "not_found", "operación inexistente")


@router.get("/v1/operations/{operation_id}")
def get_operation(operation_id: str, authorized: bool = Depends(bearer)):
    found = _get(operation_id, authorized)
    return found if isinstance(found, JSONResponse) else {"operation_id": found.id, "status": found.status}


def _approve(settings: Settings, operation: Operation, otp: str, pin: str) -> tuple[str, int | None]:
    """Decisión del usuario con OTP y PIN. Devuelve (resultado, código HTTP del callback o None).

    Resultados: `signed` (callback hecho), `invalid_credentials` (quedan intentos), `locked` (tercer fallo)
    y `not_pending` (la operación ya no estaba pendiente). La API y la página comparten esta lógica.
    """
    if operation.status != "pending":
        return "not_pending", None
    if not (hmac.compare_digest(otp, VALID_OTP) and hmac.compare_digest(pin, VALID_PIN)):
        operation.attempts += 1
        if operation.attempts >= MAX_ATTEMPTS:
            operation.status = "locked"
            return "locked", None
        return "invalid_credentials", None
    signed = _sign_pdf(settings, operation.pdf, operation.signer_cuil)
    operation.status = "signed"
    return "signed", _call_back(settings, operation, "signed", signed)


def _reject(settings: Settings, operation: Operation) -> tuple[str, int | None]:
    if operation.status != "pending":
        return "not_pending", None
    operation.status = "rejected"
    return "rejected", _call_back(settings, operation, "rejected", None)


@router.post("/v1/operations/{operation_id}/approve")
def approve(
    operation_id: str,
    body: ApprovalIn,
    authorized: bool = Depends(bearer),
    settings: Settings = Depends(enabled),
):
    """Simula al usuario autorizando en el servicio con OTP y PIN."""
    found = _get(operation_id, authorized)
    if isinstance(found, JSONResponse):
        return found
    result, code = _approve(settings, found, body.otp, body.pin)
    if result == "not_pending":
        return error(409, "not_pending", f"la operación está '{found.status}'")
    if result == "locked":
        return error(403, "locked", "operación bloqueada por intentos fallidos")
    if result == "invalid_credentials":
        return error(403, "invalid_credentials", "OTP o PIN incorrectos")
    return {"operation_id": found.id, "status": "signed", "callback_status": code}


@router.post("/v1/operations/{operation_id}/reject")
def reject(operation_id: str, authorized: bool = Depends(bearer), settings: Settings = Depends(enabled)):
    found = _get(operation_id, authorized)
    if isinstance(found, JSONResponse):
        return found
    result, code = _reject(settings, found)
    if result == "not_pending":
        return error(409, "not_pending", f"la operación está '{found.status}'")
    return {"operation_id": found.id, "status": "rejected", "callback_status": code}


# --- página de autorización (la pantalla de la persona firmante en el servicio) ----------------------

PAGE_STYLE = """
  body { font-family: system-ui, sans-serif; background: #f3f4f6; color: #111827; margin: 0; }
  main { max-width: 30rem; margin: 3rem auto; background: #fff; padding: 2rem; border-radius: .75rem;
         box-shadow: 0 1px 3px rgba(0,0,0,.15); }
  h1 { font-size: 1.25rem; margin-top: 0; }
  .tag { display: inline-block; font-size: .75rem; background: #fef3c7; color: #92400e; padding: .15rem .5rem;
         border-radius: .25rem; margin-bottom: 1rem; }
  label { display: block; margin: .75rem 0 .25rem; font-weight: 600; }
  input { width: 100%; box-sizing: border-box; padding: .5rem; font-size: 1rem; border: 1px solid #9ca3af;
          border-radius: .375rem; }
  .actions { display: flex; gap: .5rem; margin-top: 1.25rem; }
  button { padding: .6rem 1rem; font-size: 1rem; border-radius: .375rem; border: 1px solid #1d4ed8;
           background: #1d4ed8; color: #fff; cursor: pointer; }
  button.secondary { background: #fff; color: #1f2937; border-color: #9ca3af; }
  .msg { padding: .75rem 1rem; border-radius: .375rem; margin-bottom: 1rem; }
  .msg.error { background: #fee2e2; color: #991b1b; }
  .msg.ok { background: #dcfce7; color: #166534; }
  .hint { color: #4b5563; font-size: .9rem; }
"""

OUTCOMES = {
    "signed": ("ok", "Documento firmado. Esta ventana se cierra sola; si no, cerrala: Firmadoc ya tiene el resultado."),
    "rejected": ("ok", "Firma rechazada. Esta ventana se cierra sola; si no, cerrala: la solicitud quedó registrada como rechazada."),
    "locked": ("error", "Operación bloqueada por intentos fallidos. Volvé a Firmadoc y empezá de nuevo."),
    "invalid_credentials": ("error", "OTP o PIN incorrectos."),
    "not_pending": ("error", "Esta operación ya no está pendiente."),
}


def _render_page(operation: Operation, result: str | None = None) -> str:
    cuil = html.escape(operation.signer_cuil)
    parts = [
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Servicio de firma remota (simulado)</title>",
        f"<style>{PAGE_STYLE}</style></head><body><main>",
        "<span class='tag'>Servicio simulado: solo para demostración</span>",
        "<h1>Autorizar la firma del documento</h1>",
        f"<p>Firmante: CUIL <strong>{cuil}</strong>. Operación <code>{html.escape(operation.id)}</code>.</p>",
    ]
    if result is not None:
        kind, text = OUTCOMES[result]
        if result == "invalid_credentials":
            remaining = MAX_ATTEMPTS - operation.attempts
            text += f" Te quedan {remaining} intento{'s' if remaining != 1 else ''}."
        parts.append(f"<p class='msg {kind}' role='alert'>{html.escape(text)}</p>")
    if operation.status == "pending":
        parts += [
            "<form method='post'>",
            "<label for='otp'>Código de un solo uso (OTP)</label>",
            "<input id='otp' name='otp' inputmode='numeric' autocomplete='one-time-code' required autofocus>",
            "<label for='pin'>PIN del certificado remoto</label>",
            "<input id='pin' name='pin' type='password' inputmode='numeric' required>",
            "<div class='actions'>",
            "<button type='submit' name='action' value='approve'>Firmar</button>",
            "<button type='submit' name='action' value='reject' class='secondary' formnovalidate>Rechazar</button>",
            "</div></form>",
            (
                f"<p class='hint'>En el simulado el OTP es <code>{VALID_OTP}</code> y el PIN <code>{VALID_PIN}</code>; "
                "tres intentos fallidos bloquean la operación.</p>"
            ),
        ]
    else:
        parts.append(f"<p class='hint'>Estado de la operación: <strong>{html.escape(operation.status)}</strong>.</p>")
    parts.append("</main></body></html>")
    return "".join(parts)


PAGE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'",
    "Cache-Control": "no-store",
}


def _page(operation: Operation, result: str | None = None, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(_render_page(operation, result), status_code=status_code, headers=PAGE_HEADERS)


@router.get("/authorize/{operation_id}")
def authorize_page(operation_id: str):
    """Pantalla del usuario en el servicio: no exige el token OAuth (lo que lo identifica es el OTP y el PIN)."""
    operation = _operations.get(operation_id)
    if operation is None:
        raise NotFound("operación inexistente")
    return _page(operation)


@router.post("/authorize/{operation_id}")
async def authorize_submit(operation_id: str, request: Request, settings: Settings = Depends(enabled)):
    operation = _operations.get(operation_id)
    if operation is None:
        raise NotFound("operación inexistente")
    form = {k: v[0] for k, v in parse_qs((await request.body()).decode(errors="replace")).items()}
    if form.get("action") == "reject":
        result, _ = await run_in_threadpool(_reject, settings, operation)
    else:
        result, _ = await run_in_threadpool(_approve, settings, operation, form.get("otp", ""), form.get("pin", ""))
    codes = {"signed": 200, "rejected": 200, "not_pending": 409}
    return _page(operation, result, status_code=codes.get(result, 403))
