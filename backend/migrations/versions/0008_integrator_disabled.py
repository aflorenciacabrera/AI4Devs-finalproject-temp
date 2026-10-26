"""integrador deshabilitado

Revision ID: 0008
Revises: 0007

Agrega `integrating_system.disabled_at` (nulo = habilitado) para poder deshabilitar un sistema integrador
desde el panel sin borrar su historia.
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("integrating_system", sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("ALTER TABLE integrating_system DROP COLUMN disabled_at")
    else:
        op.drop_column("integrating_system", "disabled_at")
