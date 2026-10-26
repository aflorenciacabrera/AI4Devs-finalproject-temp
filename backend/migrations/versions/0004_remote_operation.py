"""operación remota de la firma (`firmar`)

Revision ID: 0004
Revises: 0003

Agrega `signature_request.remote_operation_id` (único) para ubicar la solicitud a la que corresponde
un callback del servicio de firma remota.
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signature_request", sa.Column("remote_operation_id", sa.String(length=100), nullable=True))
    op.create_index(
        "ix_signature_request_remote_operation_id", "signature_request", ["remote_operation_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_signature_request_remote_operation_id", table_name="signature_request")
    if op.get_bind().dialect.name == "sqlite":
        op.execute("ALTER TABLE signature_request DROP COLUMN remote_operation_id")
    else:
        op.drop_column("signature_request", "remote_operation_id")
