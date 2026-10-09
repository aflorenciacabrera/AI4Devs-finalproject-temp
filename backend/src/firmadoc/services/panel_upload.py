"""Carga de un PDF desde el panel de administración y creación de su solicitud de firma."""

import base64
import re
import secrets
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..errors import Unprocessable
from ..integrators import hash_api_key, new_webhook_secret
from ..models import DocumentVersion, IntegratingSystem, Provider
from ..pdf_engine import page_count
from ..providers import get_provider
from ..storage import DocumentStorage, sha256_hex
from . import admin
from . import signature_batch as batches
from . import signature_flow as flow
from .signature_flow import Ctx

PANEL_SYSTEM_NAME = "Firmadoc (panel)"
DEFAULT_SIGNER = ("Operador del panel", "panel", "panel@invalid")
PROVIDER_ORDER = (Provider.TOKEN, Provider.FIRMAR, Provider.LOCAL)


def panel_origin(settings: Settings) -> str:
    parts = urlsplit(settings.public_base_url)
    return f"{parts.scheme}://{parts.netloc}"


def panel_origins(settings: Settings) -> str:
    """Orígenes que pueden enmarcar el widget del panel: el público más los extra (servidor de desarrollo)."""
    origins = [panel_origin(settings)]
    for extra in settings.panel_origins.split(","):
        extra = extra.strip().rstrip("/")
        if extra and extra not in origins:
            origins.append(extra)
    return ",".join(origins)


def get_panel_system(db: Session, settings: Settings) -> IntegratingSystem:
    """El sistema interno de los PDF cargados desde el panel; se crea la primera vez. Sin API key utilizable.

    Sus orígenes permitidos siguen a la configuración: si cambia, se actualizan en la siguiente carga.
    """
    origins = panel_origins(settings)
    system = db.scalar(select(IntegratingSystem).where(IntegratingSystem.name == PANEL_SYSTEM_NAME))
    if system is None:
        system = IntegratingSystem(
            name=PANEL_SYSTEM_NAME,
            api_key_hash=hash_api_key("fdk_" + secrets.token_urlsafe(32)),  # el valor en claro se descarta
            allowed_origins=origins,
            webhook_secret=new_webhook_secret(),
        )
        db.add(system)
        db.flush()
    elif system.allowed_origins != origins:
        system.allowed_origins = origins
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


def _document_label(filename: str) -> str:
    """El nombre que el widget muestra para el documento (el archivo sin la extensión .pdf)."""
    name = _clean_filename(filename)
    return name[:-4] if name.lower().endswith(".pdf") else name


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
        external_document_id=_document_label(filename),
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
        "page_count": page_count(data),
        "size_bytes": len(data),
        "document_hash": version.document_hash,
    }


def _batch_providers(settings: Settings) -> list[Provider]:
    """Los métodos del lote: los habilitados entre token y local (la firma remota no se admite por lote)."""
    return [p for p in _enabled_providers(settings) if p != Provider.FIRMAR]


def upload_batch(
    db: Session,
    storage: DocumentStorage,
    settings: Settings,
    *,
    documents: list[dict],
    signer: tuple[str, str, str] | None = None,
) -> dict:
    """Varios PDF del panel como un lote del sistema interno. Es atómico: si uno es inválido no se crea nada."""
    limit = settings.max_batch_size
    if not 2 <= len(documents) <= limit:
        raise Unprocessable(f"un lote del panel admite entre 2 y {limit} documentos")
    providers = _batch_providers(settings)
    if not providers:
        raise Unprocessable("no hay ningún método de firma habilitado para lotes")
    system = get_panel_system(db, settings)
    panel_ctx = Ctx(db=db, storage=storage, settings=settings, system=system)
    name, identifier, email = signer or DEFAULT_SIGNER
    created = batches.create_batch(
        panel_ctx,
        documents=[
            {"document_base64": d["document_base64"], "external_document_id": _document_label(d["filename"])}
            for d in documents
        ],
        signer_name=name,
        signer_identifier=identifier,
        signer_email=email,
        provider=providers[0],
        callback_url=None,
        allowed_providers=providers,
    )
    # El orden de las solicitudes no está garantizado: se asocia cada archivo por el hash de su versión v1.
    pending: dict[str, list[dict]] = {}
    for d in documents:
        data = base64.b64decode(d["document_base64"])
        pending.setdefault(sha256_hex(data), []).append(
            {"filename": _clean_filename(d["filename"]), "page_count": page_count(data), "size_bytes": len(data)}
        )
    items = []
    for request in created["requests"]:
        version = db.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == request["document_id"], DocumentVersion.version_number == 1
            )
        )
        meta = pending[version.document_hash].pop(0)
        items.append({"document_id": request["document_id"], "document_hash": version.document_hash, **meta})
    admin.record(
        db,
        "panel_batch_upload",
        {
            "batch_id": str(created["id"]),
            "documents": [
                {"document_id": str(i["document_id"]), "filename": i["filename"], "document_hash": i["document_hash"]}
                for i in items
            ],
        },
    )
    db.commit()
    return {"batch_id": created["id"], "signing_url": created["signing_url"], "documents": items}
