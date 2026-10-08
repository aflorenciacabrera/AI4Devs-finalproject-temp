"""webhooks al integrador

Revision ID: 0002
Revises: 0001

Agrega `signature_request.callback_url`, `integrating_system.webhook_secret` y las columnas de
reintento de `webhook_delivery`. Solo columnas nuevas: no toca los triggers de inmutabilidad.
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signature_request", sa.Column("callback_url", sa.String(length=2000), nullable=True))
    op.add_column("integrating_system", sa.Column("webhook_secret", sa.String(length=128), nullable=True))
    op.add_column(
        "webhook_delivery",
        sa.Column("event_type", sa.String(length=40), nullable=False, server_default=""),
    )
    op.add_column("webhook_delivery", sa.Column("body", sa.Text(), nullable=False, server_default=""))
    op.add_column("webhook_delivery", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("webhook_delivery", sa.Column("last_error", sa.String(length=500), nullable=True))
    op.add_column("webhook_delivery", sa.Column("response_status", sa.Integer(), nullable=True))
    op.add_column(
        "webhook_delivery",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_webhook_delivery_due", "webhook_delivery", ["status", "next_attempt_at"]
    )


def _drop(table: str, column: str) -> None:
    # SQLite: DROP COLUMN directo (3.35+). `batch_alter_table` reconstruiría la tabla y, con las claves
    # foráneas activas y datos existentes, falla al borrar tablas referenciadas.
    if op.get_bind().dialect.name == "sqlite":
        op.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    else:
        op.drop_column(table, column)


def downgrade() -> None:
    op.drop_index("ix_webhook_delivery_due", table_name="webhook_delivery")
    for column in ("created_at", "response_status", "last_error", "next_attempt_at", "body", "event_type"):
        _drop("webhook_delivery", column)
    _drop("integrating_system", "webhook_secret")
    _drop("signature_request", "callback_url")
