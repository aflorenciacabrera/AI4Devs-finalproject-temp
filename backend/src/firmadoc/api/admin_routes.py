"""API de administración (token de administración, no API keys de integrador)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import Settings
from ..filenames import attachment_headers
from ..models import DeliveryStatus, Provider, RequestStatus
from ..services import admin, integrator_admin, panel_upload
from ..storage import DocumentStorage
from .deps import admin_auth, get_db, get_storage, settings_dep

router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(admin_auth)])


class AnchorIn(BaseModel):
    certificate_pem: str


class PanelSigner(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    identifier: str = Field(min_length=1, max_length=20)
    email: str = Field(min_length=3, max_length=320)


class SigningUploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    document_base64: str = Field(min_length=1)
    signer: PanelSigner | None = None


@router.get("/signature-requests")
def list_requests(
    integrating_system_id: uuid.UUID | None = None,
    status: RequestStatus | None = None,
    provider: Provider | None = None,
    signer: str | None = None,
    origin: str | None = None,
    q: str | None = None,
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
        origin=origin,
        q=q,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@router.get("/documents/{document_id}/custody")
def custody(document_id: uuid.UUID, db: Session = Depends(get_db)):
    return admin.custody(db, document_id)


@router.get("/documents/{document_id}/versions/{number}/download")
def download_version(
    document_id: uuid.UUID,
    number: int,
    db: Session = Depends(get_db),
    storage: DocumentStorage = Depends(get_storage),
):
    data, filename = admin.version_download(db, storage, document_id, number)
    return Response(data, media_type="application/pdf", headers=attachment_headers(filename))


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


class BatchFileIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    document_base64: str = Field(min_length=1)


class IntegratorIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    allowed_origins: list[str] = Field(default_factory=list, max_length=20)


class OriginsIn(BaseModel):
    allowed_origins: list[str] = Field(max_length=20)


class SigningBatchUploadIn(BaseModel):
    documents: list[BatchFileIn]
    signer: PanelSigner | None = None


@router.get("/integrators")
def list_integrators(db: Session = Depends(get_db)):
    return integrator_admin.list_integrators(db)


@router.post("/integrators", status_code=201)
def create_integrator(body: IntegratorIn, db: Session = Depends(get_db)):
    return integrator_admin.create(db, body.name, body.allowed_origins)


@router.patch("/integrators/{integrator_id}")
def update_integrator(integrator_id: uuid.UUID, body: OriginsIn, db: Session = Depends(get_db)):
    return integrator_admin.update_origins(db, integrator_id, body.allowed_origins)


@router.post("/integrators/{integrator_id}/rotate-webhook-secret")
def rotate_integrator_webhook_secret(integrator_id: uuid.UUID, db: Session = Depends(get_db)):
    return integrator_admin.rotate_webhook_secret(db, integrator_id)


@router.post("/integrators/{integrator_id}/rotate-api-key")
def rotate_integrator_api_key(integrator_id: uuid.UUID, db: Session = Depends(get_db)):
    return integrator_admin.rotate_api_key(db, integrator_id)


@router.post("/integrators/{integrator_id}/disable")
def disable_integrator(integrator_id: uuid.UUID, db: Session = Depends(get_db)):
    return integrator_admin.set_enabled(db, integrator_id, False)


@router.post("/integrators/{integrator_id}/enable")
def enable_integrator(integrator_id: uuid.UUID, db: Session = Depends(get_db)):
    return integrator_admin.set_enabled(db, integrator_id, True)


@router.post("/signing-batch-uploads", status_code=201)
def signing_batch_upload(
    body: SigningBatchUploadIn,
    db: Session = Depends(get_db),
    storage: DocumentStorage = Depends(get_storage),
    settings: Settings = Depends(settings_dep),
):
    signer = (body.signer.full_name, body.signer.identifier, body.signer.email) if body.signer else None
    return panel_upload.upload_batch(
        db, storage, settings, documents=[d.model_dump() for d in body.documents], signer=signer
    )


@router.post("/signing-uploads", status_code=201)
def signing_upload(
    body: SigningUploadIn,
    db: Session = Depends(get_db),
    storage: DocumentStorage = Depends(get_storage),
    settings: Settings = Depends(settings_dep),
):
    signer = (body.signer.full_name, body.signer.identifier, body.signer.email) if body.signer else None
    return panel_upload.upload(
        db, storage, settings, filename=body.filename, document_base64=body.document_base64, signer=signer
    )
