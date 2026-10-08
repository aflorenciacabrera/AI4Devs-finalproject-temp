"""binarios en la base de datos

Revision ID: 0006
Revises: 0005

Tabla `stored_blob` (almacén `database`): los PDF viven en la base, con su SHA-256. Inmutable a nivel de base
de datos: no admite UPDATE y solo admite DELETE de las referencias `prepared/…` (estado intermedio de la firma).
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

MSG = "binario inmutable (solo se descarta el estado intermedio prepared/)"


def upgrade() -> None:
    op.create_table(
        "stored_blob",
        sa.Column("ref", sa.String(length=500), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("ref", name="pk_stored_blob"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            f"""CREATE FUNCTION firmadoc_protect_blob() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' AND OLD.ref LIKE 'prepared/%' THEN RETURN OLD; END IF;
                RAISE EXCEPTION '{MSG}: %', OLD.ref;
            END; $$ LANGUAGE plpgsql"""
        )
        op.execute(
            """CREATE TRIGGER stored_blob_protect BEFORE UPDATE OR DELETE ON stored_blob
            FOR EACH ROW EXECUTE FUNCTION firmadoc_protect_blob()"""
        )
    else:
        op.execute(
            f"""CREATE TRIGGER stored_blob_no_update BEFORE UPDATE ON stored_blob
            BEGIN SELECT RAISE(ABORT, '{MSG}'); END"""
        )
        op.execute(
            f"""CREATE TRIGGER stored_blob_no_delete BEFORE DELETE ON stored_blob
            WHEN OLD.ref NOT LIKE 'prepared/%'
            BEGIN SELECT RAISE(ABORT, '{MSG}'); END"""
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER stored_blob_protect ON stored_blob")
        op.execute("DROP FUNCTION firmadoc_protect_blob()")
    else:
        op.execute("DROP TRIGGER stored_blob_no_update")
        op.execute("DROP TRIGGER stored_blob_no_delete")
    op.drop_table("stored_blob")
