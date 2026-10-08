"""eventos de administración

Revision ID: 0003
Revises: 0002

Tabla `admin_event`, append-only como `audit_event`: registra las acciones de administración que
modifican datos o configuración (anclas de confianza, rotación del certificado, reenvío de webhooks).
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

MSG_IMMUTABLE = "tabla inmutable (append-only)"
JSONType = sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "admin_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("detail", JSONType, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_admin_event"),
    )
    op.create_index("ix_admin_event_created_at", "admin_event", ["created_at"])
    if op.get_bind().dialect.name == "postgresql":
        # La función firmadoc_forbid_mutation() la crea la migración 0001.
        op.execute(
            """CREATE TRIGGER admin_event_immutable BEFORE UPDATE OR DELETE ON admin_event
            FOR EACH ROW EXECUTE FUNCTION firmadoc_forbid_mutation()"""
        )
    else:
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"""CREATE TRIGGER admin_event_no_{action.lower()} BEFORE {action} ON admin_event
                BEGIN SELECT RAISE(ABORT, '{MSG_IMMUTABLE}: admin_event'); END"""
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER admin_event_immutable ON admin_event")
    else:
        op.execute("DROP TRIGGER admin_event_no_update")
        op.execute("DROP TRIGGER admin_event_no_delete")
    op.drop_index("ix_admin_event_created_at", table_name="admin_event")
    op.drop_table("admin_event")
