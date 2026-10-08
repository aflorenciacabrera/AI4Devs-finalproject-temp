"""Carga de un PDF desde el panel de administración y creación de su solicitud de firma."""

import base64
import io
import re
import secrets
from urllib.parse import urlsplit

from pyhanko.pdf_utils.reader import PdfFileReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..errors import Unprocessable
from ..integrators import hash_api_key, new_webhook_secret
from ..models import DocumentVersion, IntegratingSystem, Provider
from ..providers import get_provider
from ..storage import DocumentStorage
from . import admin
from . import signature_flow as flow
from .signature_flow import Ctx

PANEL_SYSTEM_NAME = "Firmadoc (panel)"
DEFAULT_SIGNER = ("Operador del panel", "panel", "panel@invalid")
PROVIDER_ORDER = (Provider.TOKEN, Provider.FIRMAR, Provider.LOCAL)


def panel_origin(settings: Settings) -> str:
    parts = urlsplit(settings.public_base_url)
    return f"{parts.scheme}://{parts.netloc}"


def get_panel_system(db: Session, settings: Settings) -> IntegratingSystem:
    """El sistema interno de los PDF cargados desde el panel; se crea la primera vez. Sin API key utilizable."""
    system = db.scalar(select(IntegratingSystem).where(IntegratingSystem.name == PANEL_SYSTEM_NAME))
    if system is None:
        system = IntegratingSystem(
            name=PANEL_SYSTEM_NAME,
            api_key_hash=hash_api_key("fdk_" + secrets.token_urlsafe(32)),  # el valor en claro se descarta
            allowed_origins=panel_origin(settings),
            webhook_secret=new_webhook_secret(),
        )
        db.add(system)
        db.flush()
    return system


def _enabled_providers(settings: Settings) -> list[Provider]:
    enabled = []
    for provider in PROVIDER_ORDER:
        try:
            get_provider(provider, settings)
        except Unprocessable:
            continue
        enabled.append(provider)
    return enabled


def _clean_filename(name: str) -> str:
    name = re.sub(r"[\x00-\x1f\x7f]", "", name.replace("\\", "/").rsplit("/", 1)[-1]).strip()
    return name[:200] or "documento.pdf"


def _page_count(data: bytes) -> int:
    return int(PdfFileReader(io.BytesIO(data)).root["/Pages"]["/Count"])


def upload(
    db: Session,
    storage: DocumentStorage,
    settings: Settings,
    *,
    filename: str,
    document_base64: str,
    signer: tuple[str, str, str] | None = None,
) -> dict:
    """El documento se asigna al sistema interno del panel."""
    providers = _enabled_providers(settings)
    if not providers:
        raise Unprocessable("no hay ningún método de firma habilitado")
    system = get_panel_system(db, settings)
    panel_ctx = Ctx(db=db, storage=storage, settings=settings, system=system)
    name, identifier, email = signer or DEFAULT_SIGNER
    request = flow.create_request(
        panel_ctx,
        document_base64=document_base64,
        document_id=None,
        external_document_id=None,
        signer_name=name,
        signer_identifier=identifier,
        signer_email=email,
        provider=providers[0],
        allowed_providers=providers,
        commit=False,
    )
    version = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == request.document_id, DocumentVersion.version_number == 1
        )
    )
    data = base64.b64decode(document_base64)
    filename = _clean_filename(filename)
    admin.record(
        db,
        "panel_upload",
        {
            "document_id": str(request.document_id),
            "request_id": str(request.id),
            "filename": filename,
            "document_hash": version.document_hash,
        },
    )
    db.commit()
    return {
        "request_id": request.id,
        "document_id": request.document_id,
        "signing_url": flow.signing_url(panel_ctx, request),
        "filename": filename,
        "page_count": _page_count(data),
        "size_bytes": len(data),
        "document_hash": version.document_hash,
    }
