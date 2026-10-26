"""proveedores permitidos por solicitud

Revision ID: 0005
Revises: 0004

Agrega `signature_request.allowed_providers` (CSV, nulo = solo el proveedor de la solicitud) para que la
persona pueda elegir el método de firma desde el widget.
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signature_request", sa.Column("allowed_providers", sa.String(length=100), nullable=True))


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("ALTER TABLE signature_request DROP COLUMN allowed_providers")
    else:
        op.drop_column("signature_request", "allowed_providers")
