"""Modelo de datos (README, sección 3)."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    pass


Base.metadata.naming_convention = NAMING


def _now() -> datetime:
    return datetime.now(UTC)


def _enum(cls: type[enum.Enum]) -> Enum:
    # No nativo + CHECK: SQLite y PostgreSQL se comportan igual.
    return Enum(
        cls,
        native_enum=False,
        create_constraint=True,
        length=30,
        values_callable=lambda e: [m.value for m in e],
        name=cls.__name__.lower(),
    )


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _fk(target: str, nullable: bool = False) -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, ForeignKey(target), nullable=nullable)


def _ts(nullable: bool = False, default: bool = False) -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=nullable, default=_now if default else None
    )


JSONType = JSON().with_variant(JSONB(), "postgresql")


class Provider(enum.Enum):
    LOCAL = "local"
    TOKEN = "token"
    FIRMAR = "firmar"


class SigningStatus(enum.Enum):
    DRAFT = "draft"
    PENDING_SIGNATURE = "pending_signature"
    SIGNED = "signed"


class VersionOrigin(enum.Enum):
    UPLOADED = "uploaded"
    SIGNED = "signed"


class SignatureLevel(enum.Enum):
    B_B = "B-B"
    B_T = "B-T"
    B_LT = "B-LT"
    B_LTA = "B-LTA"


class RequestStatus(enum.Enum):
    PENDING = "pending"
    SIGNING = "signing"
    SIGNED = "signed"
    FAILED = "failed"


class BatchStatus(enum.Enum):
    PENDING = "pending"
    SIGNING = "signing"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


class RevocationStatus(enum.Enum):
    GOOD = "good"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class DeliveryStatus(enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class IntegratingSystem(Base):
    __tablename__ = "integrating_system"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(200))
    api_key_hash: Mapped[str] = mapped_column(String(128), unique=True)
    allowed_origins: Mapped[str] = mapped_column(String(2000), default="")
    webhook_secret: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = _ts(default=True)
    disabled_at: Mapped[datetime | None] = _ts(nullable=True)  # nulo = habilitado


class Signer(Base):
    __tablename__ = "signer"

    id: Mapped[uuid.UUID] = _pk()
    full_name: Mapped[str] = mapped_column(String(200))
    identifier: Mapped[str] = mapped_column(String(20))  # CUIL
    email: Mapped[str] = mapped_column(String(320))


class Certificate(Base):
    __tablename__ = "certificate"

    id: Mapped[uuid.UUID] = _pk()
    signer_id: Mapped[uuid.UUID | None] = _fk("signer.id", nullable=True)
    subject: Mapped[str] = mapped_column(String(500))
    issuer_subject: Mapped[str] = mapped_column(String(500))
    cuil: Mapped[str | None] = mapped_column(String(20), nullable=True)
    serial_number: Mapped[str] = mapped_column(String(100), unique=True)
    provider: Mapped[Provider] = mapped_column(_enum(Provider))
    revocation_status: Mapped[RevocationStatus] = mapped_column(
        _enum(RevocationStatus), default=RevocationStatus.UNKNOWN
    )
    issued_at: Mapped[datetime] = _ts()
    expires_at: Mapped[datetime] = _ts()


class Document(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = _pk()
    integrating_system_id: Mapped[uuid.UUID] = _fk("integrating_system.id")
    external_document_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("document_version.id", use_alter=True, name="fk_document_current_version"),
        nullable=True,
    )
    signing_status: Mapped[SigningStatus] = mapped_column(
        _enum(SigningStatus), default=SigningStatus.DRAFT
    )
    signature_deadline: Mapped[datetime | None] = _ts(nullable=True)
    created_at: Mapped[datetime] = _ts(default=True)

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", foreign_keys="DocumentVersion.document_id"
    )


class DocumentVersion(Base):
    """Inmutable y append-only (triggers en la migración)."""

    __tablename__ = "document_version"
    __table_args__ = (UniqueConstraint("document_id", "version_number"),)

    id: Mapped[uuid.UUID] = _pk()
    document_id: Mapped[uuid.UUID] = _fk("document.id")
    version_number: Mapped[int] = mapped_column(Integer)
    origin: Mapped[VersionOrigin] = mapped_column(_enum(VersionOrigin))
    signature_request_id: Mapped[uuid.UUID | None] = _fk("signature_request.id", nullable=True)
    signature_level: Mapped[SignatureLevel | None] = mapped_column(
        _enum(SignatureLevel), nullable=True
    )
    storage_ref: Mapped[str] = mapped_column(String(500))
    document_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = _ts(default=True)

    document: Mapped[Document] = relationship(
        back_populates="versions", foreign_keys=[document_id]
    )


class SignatureBatch(Base):
    __tablename__ = "signature_batch"

    id: Mapped[uuid.UUID] = _pk()
    integrating_system_id: Mapped[uuid.UUID] = _fk("integrating_system.id")
    signer_id: Mapped[uuid.UUID] = _fk("signer.id")
    provider: Mapped[Provider] = mapped_column(_enum(Provider))
    status: Mapped[BatchStatus] = mapped_column(_enum(BatchStatus), default=BatchStatus.PENDING)
    allowed_providers: Mapped[str | None] = mapped_column(String(100), nullable=True)  # CSV; nulo = solo `provider`
    created_at: Mapped[datetime] = _ts(default=True)
    completed_at: Mapped[datetime | None] = _ts(nullable=True)


class SignatureRequest(Base):
    __tablename__ = "signature_request"

    id: Mapped[uuid.UUID] = _pk()
    document_id: Mapped[uuid.UUID] = _fk("document.id")
    integrating_system_id: Mapped[uuid.UUID] = _fk("integrating_system.id")
    signer_id: Mapped[uuid.UUID] = _fk("signer.id")
    certificate_id: Mapped[uuid.UUID | None] = _fk("certificate.id", nullable=True)
    batch_id: Mapped[uuid.UUID | None] = _fk("signature_batch.id", nullable=True)
    provider: Mapped[Provider] = mapped_column(_enum(Provider))
    status: Mapped[RequestStatus] = mapped_column(
        _enum(RequestStatus), default=RequestStatus.PENDING
    )
    callback_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    allowed_providers: Mapped[str | None] = mapped_column(String(100), nullable=True)  # CSV; nulo = solo `provider`
    remote_operation_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )  # operación en el servicio de firma remota (`firmar`)
    created_at: Mapped[datetime] = _ts(default=True)
    signed_at: Mapped[datetime | None] = _ts(nullable=True)


class SigningChallenge(Base):
    """De un solo uso: una vez consumido no puede modificarse (trigger)."""

    __tablename__ = "signing_challenge"

    id: Mapped[uuid.UUID] = _pk()
    signature_request_id: Mapped[uuid.UUID] = _fk("signature_request.id")
    certificate_id: Mapped[uuid.UUID] = _fk("certificate.id")
    hash_to_sign: Mapped[str] = mapped_column(String(256))
    hash_algorithm: Mapped[str] = mapped_column(String(20), default="SHA-256")
    session_ref: Mapped[str] = mapped_column(String(200))
    expires_at: Mapped[datetime] = _ts()
    consumed_at: Mapped[datetime | None] = _ts(nullable=True)
    created_at: Mapped[datetime] = _ts(default=True)


class AuditEvent(Base):
    """Append-only (triggers en la migración). Exactamente una referencia."""

    __tablename__ = "audit_event"
    __table_args__ = (
        CheckConstraint(
            "(signature_request_id IS NULL) <> (batch_id IS NULL)", name="exactly_one_ref"
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    signature_request_id: Mapped[uuid.UUID | None] = _fk("signature_request.id", nullable=True)
    batch_id: Mapped[uuid.UUID | None] = _fk("signature_batch.id", nullable=True)
    event_type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = _ts(default=True)


class WebhookDelivery(Base):
    __tablename__ = "webhook_delivery"

    id: Mapped[uuid.UUID] = _pk()
    signature_request_id: Mapped[uuid.UUID] = _fk("signature_request.id")
    url: Mapped[str] = mapped_column(String(2000))
    status: Mapped[DeliveryStatus] = mapped_column(
        _enum(DeliveryStatus), default=DeliveryStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = _ts(nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), default="", server_default="")
    body: Mapped[str] = mapped_column(Text, default="", server_default="")  # JSON fijo del evento
    next_attempt_at: Mapped[datetime | None] = _ts(nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )


class AdminEvent(Base):
    """Append-only (triggers en la migración 0003): acciones de administración que modifican algo."""

    __tablename__ = "admin_event"

    id: Mapped[uuid.UUID] = _pk()
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )


class StoredBlob(Base):
    """Binario guardado en la base (almacén `database`). Inmutable: triggers en la migración 0006
    (solo las referencias `prepared/…`, estado intermedio de una firma, se pueden borrar)."""

    __tablename__ = "stored_blob"

    ref: Mapped[str] = mapped_column(String(500), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
