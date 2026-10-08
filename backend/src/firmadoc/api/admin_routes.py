"""API de administración (token de administración, no API keys de integrador)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import DeliveryStatus, Provider, RequestStatus
from ..services import admin
from .deps import admin_auth, get_db, settings_dep

router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(admin_auth)])


class AnchorIn(BaseModel):
    certificate_pem: str


@router.get("/signature-requests")
def list_requests(
    integrating_system_id: uuid.UUID | None = None,
    status: RequestStatus | None = None,
    provider: Provider | None = None,
    signer: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return admin.list_requests(
        db,
        integrating_system_id=integrating_system_id,
        status=status,
        provider=provider,
        signer=signer,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@router.get("/documents/{document_id}/custody")
def custody(document_id: uuid.UUID, db: Session = Depends(get_db)):
    return admin.custody(db, document_id)


@router.get("/webhook-deliveries")
def list_deliveries(
    status: DeliveryStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return admin.list_deliveries(db, status=status, limit=limit, offset=offset)


@router.post("/webhook-deliveries/{delivery_id}/retry")
def retry_delivery(delivery_id: uuid.UUID, db: Session = Depends(get_db)):
    return admin.retry_delivery(db, delivery_id)


@router.get("/events")
def list_events(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    return admin.list_events(db, limit=limit, offset=offset)


@router.get("/trust-anchors")
def list_anchors(settings: Settings = Depends(settings_dep)):
    return admin.list_anchors(settings)


@router.post("/trust-anchors", status_code=201)
def add_anchor(body: AnchorIn, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)):
    return admin.add_anchor(db, settings, body.certificate_pem)


@router.delete("/trust-anchors/{fingerprint}")
def remove_anchor(
    fingerprint: str, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)
):
    return admin.remove_anchor(db, settings, fingerprint)


@router.get("/local-certificate")
def local_certificate(settings: Settings = Depends(settings_dep)):
    return admin.local_certificate_info(settings)


@router.post("/local-certificate/rotate")
def rotate_local_certificate(
    db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)
):
    return admin.rotate_local_certificate(db, settings)
