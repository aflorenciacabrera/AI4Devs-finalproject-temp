import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..models import Provider, SigningStatus


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
    allowed_providers: list[Provider] | None = None  # métodos que la persona puede elegir en el widget


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


class RemoteInfo(BaseModel):
    operation_id: str
    authorization_url: str


class PrepareResponse(BaseModel):
    challenges: list[Challenge]
    expires_at: datetime
    remote: RemoteInfo | None = None


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


class SelectProviderBody(BaseModel):
    provider: Provider


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
    allowed_providers: list[str]
    token_expires_at: datetime
    signed_at: datetime | None = None
    certificate: WidgetCertificate | None = None
    document: DocumentBlock | None = None
    signing_status: str | None = None
    signature_deadline: datetime | None = None
    page_count: int | None = None
    size_bytes: int | None = None


class BatchError(BaseModel):
    code: str | None
    detail: str
    http_status: int


class WidgetBatchItem(BaseModel):
    signature_request_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page_count: int | None = None
    size_bytes: int | None = None
    status: str
    version_number: int | None = None
    error: BatchError | None = None


class WidgetBatchContext(BaseModel):
    id: uuid.UUID
    status: str
    provider: str
    allowed_providers: list[str]
    signer_name: str
    allowed_origins: list[str]
    agent_url: str
    token_expires_at: datetime
    completed_at: datetime | None = None
    documents: list[WidgetBatchItem]


class RetryOut(BaseModel):
    id: uuid.UUID
    signing_url: str


class BatchDocumentIn(BaseModel):
    document_base64: str | None = None
    document_id: uuid.UUID | None = None
    external_document_id: str | None = Field(default=None, max_length=200)


class CreateSignatureBatch(BaseModel):
    documents: list[BatchDocumentIn]
    signer: SignerIn
    provider: Provider
    callback_url: str | None = None
    allowed_providers: list[Provider] | None = None  # métodos que la persona puede elegir en el widget


class BatchChallenge(Challenge):
    signature_request_id: uuid.UUID


class BatchPrepareResponse(BaseModel):
    challenges: list[BatchChallenge]
    expires_at: datetime


class BatchItem(BaseModel):
    signature_request_id: uuid.UUID
    document_id: uuid.UUID
    status: str
    version_number: int | None
    download_url: str | None
    error: BatchError | None = None


class SignatureBatchOut(BaseModel):
    id: uuid.UUID
    status: str
    provider: str
    created_at: datetime
    completed_at: datetime | None
    requests: list[BatchItem]
    signing_url: str | None = None  # solo al crear el lote


class DocumentOut(BaseModel):
    id: uuid.UUID
    external_document_id: str | None
    signing_status: str
    signature_deadline: datetime | None
    deadline_passed: bool
    current_version_number: int | None
    download_url: str | None


class UpdateDocument(BaseModel):
    signing_status: SigningStatus | None = None
    signature_deadline: datetime | None = None


class SignatureEntryCertificate(BaseModel):
    subject: str
    issuer_subject: str
    serial_number: str


class SignatureEntry(BaseModel):
    version_number: int
    signer_name: str
    signer_identifier: str
    signed_at: datetime | None
    provider: str
    certificate: SignatureEntryCertificate | None


class TimestampCheckOut(BaseModel):
    present: bool
    time: str | None
    intact: bool
    valid: bool
    trusted: bool


class SignatureCheckOut(BaseModel):
    field_name: str
    signer_subject: str
    serial_number: str
    claimed_signing_time: str | None
    intact: bool
    valid: bool
    trusted: bool
    modification_level: str
    ok: bool
    timestamp: TimestampCheckOut


class VerifyOut(BaseModel):
    document_id: uuid.UUID
    version_number: int
    hash_matches: bool
    signatures: list[SignatureCheckOut]
    valid: bool
    checked_at: datetime
