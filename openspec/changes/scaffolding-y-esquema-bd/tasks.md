## 1. Estructura del repositorio y tooling

- [x] 1.1 Crear `backend/src/firmadoc/`, `tests/`, `widget/README.md` y `agent/README.md` (propósito y ticket FIRDOC que los implementa)
- [x] 1.2 Crear `pyproject.toml` (Python >=3.11, dependencias de backend y extras `dev` con pytest y ruff, configuración de pytest y ruff)
- [x] 1.3 Crear `config.py` con `pydantic-settings` y `FIRMADOC_DATABASE_URL` (SQLite por defecto) y `.env.example`
- [x] 1.4 Crear la app FastAPI con `GET /health` y test del endpoint
- [x] 1.5 Crear `docker-compose.yml` con PostgreSQL para tests y desarrollo, y documentar el arranque en el README del backend

## 2. Modelos SQLAlchemy

- [x] 2.1 Crear base declarativa, tipos comunes (`Uuid`, `JSON`/`JSONB`) y enums con `CHECK`
- [x] 2.2 Modelar `IntegratingSystem`, `Signer` y `Certificate` (unicidad de `api_key_hash` y `serial_number`)
- [x] 2.3 Modelar `Document` y `DocumentVersion` (FK circular con `use_alter`, índice único `(document_id, version_number)`)
- [x] 2.4 Modelar `SignatureRequest`, `SignatureBatch` y `SigningChallenge`
- [x] 2.5 Modelar `AuditEvent` (CHECK de exactamente una referencia) y `WebhookDelivery`
- [x] 2.6 Activar `PRAGMA foreign_keys=ON` para SQLite en la creación del engine

## 3. Migración Alembic

- [x] 3.1 Configurar Alembic (`alembic.ini`, `env.py` leyendo `FIRMADOC_DATABASE_URL`)
- [x] 3.2 Escribir la migración inicial con las 10 tablas, FKs, CHECK e índices
- [x] 3.3 Agregar triggers de inmutabilidad para PostgreSQL (`document_version`, `audit_event`, `signing_challenge`)
- [x] 3.4 Agregar los equivalentes para SQLite
- [x] 3.5 Implementar `downgrade` completo (elimina triggers y tablas)

## 4. Seed de demostración

- [x] 4.1 Implementar `seed_demo(session)` idempotente (sistema integrador con API key solo en hash, documento con dos versiones `uploaded` y `signed`, certificado demo, firmante)
- [x] 4.2 Exponerlo como `python -m firmadoc.seed`

## 5. Tests

- [x] 5.1 Fixture de base parametrizada por motor (SQLite siempre; PostgreSQL con `FIRMADOC_TEST_PG_URL`, si no `skip`) que aplica la migración con Alembic
- [x] 5.2 Test: `upgrade head` crea las 10 tablas y `downgrade base` las elimina
- [x] 5.3 Test: `UPDATE`/`DELETE` sobre `document_version` y `audit_event` fallan
- [x] 5.4 Test: `(document_id, version_number)` duplicado falla y actualizar `current_version_id` no toca `document_version`
- [x] 5.5 Test: `audit_event` rechaza cero o dos referencias
- [x] 5.6 Test: un desafío consumido no puede modificarse
- [x] 5.7 Test: `serial_number` y `api_key_hash` duplicados fallan
- [x] 5.8 Test: el seed es idempotente
- [x] 5.9 Ejecutar `pytest` y `ruff check` sin errores
