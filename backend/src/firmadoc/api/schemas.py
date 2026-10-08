import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..models import Provider


class SignerIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    identifier: str = Field(min_length=1, max_length=20)  # CUIL
    email: str = Field(min_length=3, max_length=320)


class CreateSignatureRequest(BaseModel):
    document_base64: str | None = None
    document_id: uuid.UUID | None = None
    external_document_id: str | None = Field(default=None, max_length=200)
    signer: SignerIn
    provider: Provider
    callback_url: str | None = None  # https; se notifica al completarse o fallar


class SignatureRequestCreated(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: str
    signing_url: str
    created_at: datetime


class PrepareBody(BaseModel):
    certificate_pem: str | None = None


class Challenge(BaseModel):
    challenge_id: uuid.UUID
    document_name: str
    hash_algorithm: str
    hash_to_sign: str


class PrepareResponse(BaseModel):
    challenges: list[Challenge]
    expires_at: datetime


class SignatureIn(BaseModel):
    challenge_id: uuid.UUID
    signature_base64: str


class CompleteBody(BaseModel):
    signatures: list[SignatureIn] = []


class CertificateOut(BaseModel):
    subject: str
    serial_number: str


class DocumentBlock(BaseModel):
    id: uuid.UUID
    external_document_id: str | None
    version_number: int
    is_active_version: bool
    signing_status: str
    signature_level: str | None
    download_url: str
    signed_document_base64: str | None


class EventOut(BaseModel):
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class SignatureRequestOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: str
    provider: str
    signing_url: str
    created_at: datetime
    certificate: CertificateOut | None = None
    document: DocumentBlock | None = None
    events: list[EventOut] = []


class WidgetCertificate(BaseModel):
    subject: str
    issuer_subject: str
    serial_number: str


class WidgetContext(BaseModel):
    id: uuid.UUID
    status: str
    provider: str
    document_name: str
    signer_name: str
    allowed_origins: list[str]
    agent_url: str
    token_expires_at: datetime
    signed_at: datetime | None = None
    certificate: WidgetCertificate | None = None
    document: DocumentBlock | None = None
