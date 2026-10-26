"""esquema inicial

Revision ID: 0001
Revises: 
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


MSG_IMMUTABLE = "tabla inmutable (append-only)"
MSG_CONSUMED = "desafio ya consumido: no puede modificarse"


def _create_immutability_triggers() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"""
            CREATE FUNCTION firmadoc_forbid_mutation() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION '{MSG_IMMUTABLE}: %', TG_TABLE_NAME; END;
            $$ LANGUAGE plpgsql""")
        op.execute(f"""
            CREATE FUNCTION firmadoc_challenge_single_use() RETURNS trigger AS $$
            BEGIN
                IF OLD.consumed_at IS NOT NULL THEN RAISE EXCEPTION '{MSG_CONSUMED}'; END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql""")
        for table in ("document_version", "audit_event"):
            op.execute(f"""CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION firmadoc_forbid_mutation()""")
        op.execute("""CREATE TRIGGER signing_challenge_single_use BEFORE UPDATE ON signing_challenge
            FOR EACH ROW EXECUTE FUNCTION firmadoc_challenge_single_use()""")
    else:
        for table in ("document_version", "audit_event"):
            for action in ("UPDATE", "DELETE"):
                op.execute(f"""CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table}
                    BEGIN SELECT RAISE(ABORT, '{MSG_IMMUTABLE}: {table}'); END""")
        op.execute(f"""CREATE TRIGGER signing_challenge_single_use BEFORE UPDATE ON signing_challenge
            WHEN OLD.consumed_at IS NOT NULL
            BEGIN SELECT RAISE(ABORT, '{MSG_CONSUMED}'); END""")


def _drop_immutability_triggers() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in ("document_version", "audit_event"):
            op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
        op.execute("DROP TRIGGER signing_challenge_single_use ON signing_challenge")
        op.execute("DROP FUNCTION firmadoc_forbid_mutation()")
        op.execute("DROP FUNCTION firmadoc_challenge_single_use()")
    else:
        for table in ("document_version", "audit_event"):
            for action in ("update", "delete"):
                op.execute(f"DROP TRIGGER {table}_no_{action}")
        op.execute("DROP TRIGGER signing_challenge_single_use")


def upgrade() -> None:
    op.create_table('integrating_system',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('api_key_hash', sa.String(length=128), nullable=False),
    sa.Column('allowed_origins', sa.String(length=2000), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_integrating_system')),
    sa.UniqueConstraint('api_key_hash', name=op.f('uq_integrating_system_api_key_hash'))
    )
    op.create_table('signer',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('identifier', sa.String(length=20), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_signer'))
    )
    op.create_table('certificate',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('signer_id', sa.Uuid(), nullable=True),
    sa.Column('subject', sa.String(length=500), nullable=False),
    sa.Column('issuer_subject', sa.String(length=500), nullable=False),
    sa.Column('cuil', sa.String(length=20), nullable=True),
    sa.Column('serial_number', sa.String(length=100), nullable=False),
    sa.Column('provider', sa.Enum('local', 'token', 'firmar', name='provider', native_enum=False, create_constraint=False, length=30), nullable=False),
    sa.Column('revocation_status', sa.Enum('good', 'revoked', 'unknown', name='revocationstatus', native_enum=False, create_constraint=False, length=30), nullable=False),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("provider IN ('local', 'token', 'firmar')", name=op.f('ck_certificate_provider')),
    sa.CheckConstraint("revocation_status IN ('good', 'revoked', 'unknown')", name=op.f('ck_certificate_revocationstatus')),
    sa.ForeignKeyConstraint(['signer_id'], ['signer.id'], name=op.f('fk_certificate_signer_id_signer')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_certificate')),
    sa.UniqueConstraint('serial_number', name=op.f('uq_certificate_serial_number'))
    )
    op.create_table('document',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('integrating_system_id', sa.Uuid(), nullable=False),
    sa.Column('external_document_id', sa.String(length=200), nullable=True),
    sa.Column('current_version_id', sa.Uuid(), nullable=True),
    sa.Column('signing_status', sa.Enum('draft', 'pending_signature', 'signed', name='signingstatus', native_enum=False, create_constraint=False, length=30), nullable=False),
    sa.Column('signature_deadline', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("signing_status IN ('draft', 'pending_signature', 'signed')", name=op.f('ck_document_signingstatus')),
    sa.ForeignKeyConstraint(['integrating_system_id'], ['integrating_system.id'], name=op.f('fk_document_integrating_system_id_integrating_system')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document'))
    )
    op.create_table('signature_batch',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('integrating_system_id', sa.Uuid(), nullable=False),
    sa.Column('signer_id', sa.Uuid(), nullable=False),
    sa.Column('provider', sa.Enum('local', 'token', 'firmar', name='provider', native_enum=False, create_constraint=False, length=30), nullable=False),
    sa.Column('status', sa.Enum('pending', 'signing', 'completed', 'partial_failure', 'failed', name='batchstatus', native_enum=False, create_constraint=False, length=30), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("provider IN ('local', 'token', 'firmar')", name=op.f('ck_signature_batch_provider')),
    sa.CheckConstraint("status IN ('pending', 'signing', 'completed', 'partial_failure', 'failed')", name=op.f('ck_signature_batch_batchstatus')),
    sa.ForeignKeyConstraint(['integrating_system_id'], ['integrating_system.id'], name=op.f('fk_signature_batch_integrating_system_id_integrating_system')),
    sa.ForeignKeyConstraint(['signer_id'], ['signer.id'], name=op.f('fk_signature_batch_signer_id_signer')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_signature_batch'))
    )
    op.create_table('signature_request',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('integrating_system_id', sa.Uuid(), nullable=False),
    sa.Column('signer_id', sa.Uuid(), nullable=False),
    sa.Column('certificate_id', sa.Uuid(), nullable=True),
    sa.Column('batch_id', sa.Uuid(), nullable=True),
    sa.Column('provider', sa.Enum('local', 'token', 'firmar', name='provider', native_enum=False, create_constraint=False, length=30), nullable=False),
    sa.Column('status', sa.Enum('pending', 'signing', 'signed', 'failed', name='requeststatus', native_enum=False, create_constraint=False, length=30), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("provider IN ('local', 'token', 'firmar')", name=op.f('ck_signature_request_provider')),
    sa.CheckConstraint("status IN ('pending', 'signing', 'signed', 'failed')", name=op.f('ck_signature_request_requeststatus')),
    sa.ForeignKeyConstraint(['batch_id'], ['signature_batch.id'], name=op.f('fk_signature_request_batch_id_signature_batch')),
    sa.ForeignKeyConstraint(['certificate_id'], ['certificate.id'], name=op.f('fk_signature_request_certificate_id_certificate')),
    sa.ForeignKeyConstraint(['document_id'], ['document.id'], name=op.f('fk_signature_request_document_id_document')),
    sa.ForeignKeyConstraint(['integrating_system_id'], ['integrating_system.id'], name=op.f('fk_signature_request_integrating_system_id_integrating_system')),
    sa.ForeignKeyConstraint(['signer_id'], ['signer.id'], name=op.f('fk_signature_request_signer_id_signer')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_signature_request'))
    )
    op.create_table('audit_event',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('signature_request_id', sa.Uuid(), nullable=True),
    sa.Column('batch_id', sa.Uuid(), nullable=True),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('payload', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('(signature_request_id IS NULL) <> (batch_id IS NULL)', name=op.f('ck_audit_event_exactly_one_ref')),
    sa.ForeignKeyConstraint(['batch_id'], ['signature_batch.id'], name=op.f('fk_audit_event_batch_id_signature_batch')),
    sa.ForeignKeyConstraint(['signature_request_id'], ['signature_request.id'], name=op.f('fk_audit_event_signature_request_id_signature_request')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_event'))
    )
    op.create_table('document_version',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('origin', sa.Enum('uploaded', 'signed', name='versionorigin', native_enum=False, create_constraint=False, length=30), nullable=False),
    sa.Column('signature_request_id', sa.Uuid(), nullable=True),
    sa.Column('signature_level', sa.Enum('B-B', 'B-T', 'B-LT', 'B-LTA', name='signaturelevel', native_enum=False, create_constraint=False, length=30), nullable=True),
    sa.Column('storage_ref', sa.String(length=500), nullable=False),
    sa.Column('document_hash', sa.String(length=128), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("origin IN ('uploaded', 'signed')", name=op.f('ck_document_version_versionorigin')),
    sa.CheckConstraint("signature_level IN ('B-B', 'B-T', 'B-LT', 'B-LTA')", name=op.f('ck_document_version_signaturelevel')),
    sa.ForeignKeyConstraint(['document_id'], ['document.id'], name=op.f('fk_document_version_document_id_document')),
    sa.ForeignKeyConstraint(['signature_request_id'], ['signature_request.id'], name=op.f('fk_document_version_signature_request_id_signature_request')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_version')),
    sa.UniqueConstraint('document_id', 'version_number', name=op.f('uq_document_version_document_id'))
    )
    op.create_table('signing_challenge',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('signature_request_id', sa.Uuid(), nullable=False),
    sa.Column('certificate_id', sa.Uuid(), nullable=False),
    sa.Column('hash_to_sign', sa.String(length=256), nullable=False),
    sa.Column('hash_algorithm', sa.String(length=20), nullable=False),
    sa.Column('session_ref', sa.String(length=200), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['certificate_id'], ['certificate.id'], name=op.f('fk_signing_challenge_certificate_id_certificate')),
    sa.ForeignKeyConstraint(['signature_request_id'], ['signature_request.id'], name=op.f('fk_signing_challenge_signature_request_id_signature_request')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_signing_challenge'))
    )
    op.create_table('webhook_delivery',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('signature_request_id', sa.Uuid(), nullable=False),
    sa.Column('url', sa.String(length=2000), nullable=False),
    sa.Column('status', sa.Enum('pending', 'delivered', 'failed', name='deliverystatus', native_enum=False, create_constraint=False, length=30), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('pending', 'delivered', 'failed')", name=op.f('ck_webhook_delivery_deliverystatus')),
    sa.ForeignKeyConstraint(['signature_request_id'], ['signature_request.id'], name=op.f('fk_webhook_delivery_signature_request_id_signature_request')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_webhook_delivery'))
    )
    # FK circular document -> document_version (batch: compatible con SQLite)
    with op.batch_alter_table("document") as batch:
        batch.create_foreign_key(
            "fk_document_current_version", "document_version", ["current_version_id"], ["id"]
        )
    _create_immutability_triggers()


def downgrade() -> None:
    _drop_immutability_triggers()
    with op.batch_alter_table("document") as batch:
        batch.drop_constraint("fk_document_current_version", type_="foreignkey")
    op.drop_table('webhook_delivery')
    op.drop_table('signing_challenge')
    op.drop_table('document_version')
    op.drop_table('audit_event')
    op.drop_table('signature_request')
    op.drop_table('signature_batch')
    op.drop_table('document')
    op.drop_table('certificate')
    op.drop_table('signer')
    op.drop_table('integrating_system')
