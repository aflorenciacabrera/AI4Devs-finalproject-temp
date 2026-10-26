"""proveedores permitidos por lote

Revision ID: 0007
Revises: 0006

Agrega `signature_batch.allowed_providers` (CSV, nulo = solo el proveedor del lote) para que la persona
pueda elegir el método de firma desde el widget de lote.
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signature_batch", sa.Column("allowed_providers", sa.String(length=100), nullable=True))


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("ALTER TABLE signature_batch DROP COLUMN allowed_providers")
    else:
        op.drop_column("signature_batch", "allowed_providers")
