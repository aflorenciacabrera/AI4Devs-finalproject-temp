"""Callback del servicio de firma remota (`firmar`)."""

from fastapi import APIRouter, Depends, Header, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..config import Settings
from ..providers.firmar import SIGNATURE_HEADER
from ..services import remote_signing
from ..storage import DocumentStorage
from .deps import get_db, get_storage, settings_dep

router = APIRouter(prefix="/api/v1/providers/firmar")


@router.post("/callback")
async def callback(
    request: Request,
    x_firmar_signature: str | None = Header(default=None, alias=SIGNATURE_HEADER),
    db: Session = Depends(get_db),
    storage: DocumentStorage = Depends(get_storage),
    settings: Settings = Depends(settings_dep),
):
    raw = await request.body()  # la firma HMAC se calcula sobre los bytes exactos recibidos
    return await run_in_threadpool(
        remote_signing.handle_callback, db, storage, settings, raw, x_firmar_signature
    )
