## Context

Repositorio nuevo, sin código. El diseño de datos está definido en la sección 3 del README (modelo, entidades, restricciones). Se debe poder desarrollar en una PC Windows sin servicios extra (SQLite) y validar contra PostgreSQL (Docker disponible), que es el destino real (`jsonb`, triggers).

## Goals / Non-Goals

**Goals:**
- Que el esquema haga cumplir por sí mismo la inmutabilidad y el uso único, sin depender de que la aplicación se porte bien.
- Que los mismos tests corran contra SQLite y PostgreSQL.

**Non-Goals:**
- Lógica de negocio, endpoints de firma, repositorios o servicios; almacenamiento real de binarios.

## Decisions

1. **SQLAlchemy 2.0 (estilo declarativo tipado) + Alembic.** Migraciones escritas a mano (no autogeneradas a ciegas) porque incluyen triggers. Alternativa descartada: SQLModel, por menor control sobre constraints y enums.
2. **IDs `uuid` generados en la aplicación** (`uuid4`), tipo `Uuid` de SQLAlchemy (nativo en PostgreSQL, `CHAR(32)` en SQLite).
3. **Enums como `Enum` nativo de SQLAlchemy con `native_enum=False` + `CHECK`**, para que SQLite y PostgreSQL se comporten igual y las migraciones futuras no requieran `ALTER TYPE`.
4. **`payload` como `JSON` con variante `JSONB` en PostgreSQL** (`JSON().with_variant(JSONB, "postgresql")`).
5. **Inmutabilidad con triggers**, un par por motor, creados en la migración:
   - `document_version` y `audit_event`: `BEFORE UPDATE` y `BEFORE DELETE` que lanzan error (`RAISE EXCEPTION` en PostgreSQL, `RAISE(ABORT, ...)` en SQLite).
   - `signing_challenge`: `BEFORE UPDATE` que aborta si `OLD.consumed_at IS NOT NULL`.
   Alternativa descartada: rol de aplicación sin permisos `UPDATE`/`DELETE`; se puede sumar en despliegue, pero no es testeable en SQLite ni en CI simple.
6. **`audit_event` con `CHECK ((signature_request_id IS NULL) <> (batch_id IS NULL))`** — exactamente uno.
7. **Ciclo `Document` ↔ `DocumentVersion`**: `Document.current_version_id` es FK nullable con `use_alter=True` (se crea tras ambas tablas) para evitar la dependencia circular.
8. **Configuración** con `pydantic-settings` y la variable `FIRMADOC_DATABASE_URL` (SQLite por defecto). `backend/` es un paquete Python (`firmadoc`) bajo `backend/src/firmadoc/`.
9. **Tests**: fixture parametrizada por motor. SQLite siempre; PostgreSQL solo si `FIRMADOC_TEST_PG_URL` está definida (se levanta con `docker compose` provisto), y se marca `skip` si no.
10. **Seed** como función idempotente `seed_demo(session)` invocable por CLI (`python -m firmadoc.seed`); la API key demo se guarda solo como hash.

## Risks / Trade-offs

- Sintaxis de triggers distinta por motor → dos implementaciones a mantener; mitigado por tests idénticos en ambos.
- SQLite no impone tipos con rigor ni `ON DELETE` por defecto → se activa `PRAGMA foreign_keys=ON` en cada conexión.
- Triggers dificultan correcciones de datos de demo → el seed se recrea borrando la base, no modificando filas.
- `storage_ref` queda sin implementación real: las versiones del seed usan referencias ficticias.

## Open Questions

- ¿Postgres como BD de desarrollo por defecto en el futuro? Por ahora SQLite por simplicidad.
