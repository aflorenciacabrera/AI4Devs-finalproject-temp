"""Migración 0002 (webhooks): reversible, conserva los datos y no toca los triggers."""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import command

from firmadoc.db import make_engine

from .conftest import alembic_config

NEW_COLUMNS = {
    "signature_request": {"callback_url"},
    "integrating_system": {"webhook_secret"},
    "webhook_delivery": {"event_type", "body", "next_attempt_at", "last_error", "response_status", "created_at"},
}
TRIGGERS = {
    "document_version_no_update",
    "document_version_no_delete",
    "audit_event_no_update",
    "audit_event_no_delete",
    "signing_challenge_single_use",
}


def columns(engine, table):
    return {c["name"] for c in sa.inspect(engine).get_columns(table)}


def triggers(engine) -> set[str]:
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            rows = conn.execute(sa.text("select name from sqlite_master where type='trigger'"))
        else:
            rows = conn.execute(sa.text("select tgname from pg_trigger where not tgisinternal"))
        found = {r[0] for r in rows}
    if engine.dialect.name == "postgresql":  # nombres equivalentes en PostgreSQL
        found = {n.replace("_immutable", "_no_update") for n in found}
        found |= {"document_version_no_delete", "audit_event_no_delete"} if found else set()
    return found


def seed_old_schema(engine) -> uuid.UUID:
    """Datos creados con el esquema 0001 (antes de la migración)."""
    ids = {k: uuid.uuid4() for k in ("system", "signer", "document", "request")}
    now = datetime.now(UTC)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "insert into integrating_system (id, name, api_key_hash, allowed_origins, created_at) "
                "values (:id, 'previo', 'hash-previo', 'https://a.example.org', :now)"
            ).bindparams(sa.bindparam("id", type_=sa.Uuid), sa.bindparam("now", type_=sa.DateTime(timezone=True))),
            {"id": ids["system"], "now": now},
        )
        conn.execute(
            sa.text("insert into signer (id, full_name, identifier, email) values (:id, 'A', '20111111112', 'a@x.org')")
            .bindparams(sa.bindparam("id", type_=sa.Uuid)),
            {"id": ids["signer"]},
        )
        conn.execute(
            sa.text(
                "insert into document (id, integrating_system_id, signing_status, created_at) "
                "values (:id, :sid, 'draft', :now)"
            ).bindparams(
                sa.bindparam("id", type_=sa.Uuid),
                sa.bindparam("sid", type_=sa.Uuid),
                sa.bindparam("now", type_=sa.DateTime(timezone=True)),
            ),
            {"id": ids["document"], "sid": ids["system"], "now": now},
        )
        conn.execute(
            sa.text(
                "insert into signature_request (id, document_id, integrating_system_id, signer_id, provider, "
                "status, created_at) values (:id, :doc, :sid, :signer, 'local', 'pending', :now)"
            ).bindparams(
                sa.bindparam("id", type_=sa.Uuid),
                sa.bindparam("doc", type_=sa.Uuid),
                sa.bindparam("sid", type_=sa.Uuid),
                sa.bindparam("signer", type_=sa.Uuid),
                sa.bindparam("now", type_=sa.DateTime(timezone=True)),
            ),
            {"id": ids["request"], "doc": ids["document"], "sid": ids["system"], "signer": ids["signer"], "now": now},
        )
    return ids["request"]


def test_migracion_conserva_datos_y_triggers_y_es_reversible(db_url):
    cfg = alembic_config(db_url)
    command.upgrade(cfg, "0001")
    engine = make_engine(db_url)
    before = triggers(engine)
    assert before  # el esquema 0001 trae los triggers de inmutabilidad
    for table, new in NEW_COLUMNS.items():
        assert not new & columns(engine, table)
    request_id = seed_old_schema(engine)

    command.upgrade(cfg, "0002")
    for table, new in NEW_COLUMNS.items():
        assert new <= columns(engine, table), table
    assert triggers(engine) == before  # los triggers siguen vigentes

    with engine.connect() as conn:  # los datos previos se conservan y las columnas nuevas quedan nulas
        row = conn.execute(
            sa.text("select callback_url from signature_request where id = :id").bindparams(
                sa.bindparam("id", type_=sa.Uuid)
            ),
            {"id": request_id},
        ).one()
        assert row[0] is None
        assert conn.execute(sa.text("select count(*) from integrating_system where name = 'previo'")).scalar() == 1
        assert conn.execute(sa.text("select webhook_secret from integrating_system")).scalar() is None

    command.downgrade(cfg, "0001")
    for table, new in NEW_COLUMNS.items():
        assert not new & columns(engine, table), table
    assert triggers(engine) == before
    with engine.connect() as conn:
        assert conn.execute(sa.text("select count(*) from signature_request")).scalar() == 1  # no se perdió nada

    command.upgrade(cfg, "head")  # y se puede volver a aplicar
    assert NEW_COLUMNS["webhook_delivery"] <= columns(engine, "webhook_delivery")
    engine.dispose()
