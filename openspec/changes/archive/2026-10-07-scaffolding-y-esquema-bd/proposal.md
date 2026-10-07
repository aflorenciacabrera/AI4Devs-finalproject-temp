## Why

Firmadoc no tiene código todavía: la Entrega 1 es 100% documentación. Todo el backlog (flujo de firma diferida, webhooks, widget, agente) depende de un repositorio estructurado y de un esquema de base de datos que haga cumplir por sí mismo las garantías del diseño (versiones inmutables, auditoría append-only, desafíos de un solo uso). Este change es el prerrequisito de FIRDOC-23 (HU1), FIRDOC-29 y FIRDOC-6.

Backlog: FIRDOC-28.

## What Changes

- Estructura del repositorio: `backend/` (FastAPI + SQLAlchemy + Alembic), `widget/` y `agent/` con README y sin código, `tests/`.
- `pyproject.toml` con dependencias de backend y de desarrollo (pytest, ruff), y un endpoint `GET /health` mínimo para validar que la app levanta.
- Modelos SQLAlchemy de las 10 entidades de la sección 3 del README: `IntegratingSystem`, `Document`, `DocumentVersion`, `SignatureRequest`, `SigningChallenge`, `SignatureBatch`, `Signer`, `Certificate`, `AuditEvent`, `WebhookDelivery`.
- Migración inicial Alembic con las restricciones de integridad: `document_version` y `audit_event` rechazan `UPDATE`/`DELETE` a nivel de base de datos, índice único `(document_id, version_number)`, consumo único de desafíos, `audit_event` con exactamente uno de `signature_request_id` / `batch_id`.
- Script de seed de demo (un sistema integrador, un documento con dos versiones, un certificado demo).
- Tests pytest del esquema contra SQLite y PostgreSQL.

## Capabilities

### New Capabilities

- `project-scaffolding`: estructura del repo, arranque de la app y herramientas de desarrollo.
- `data-model`: esquema relacional inicial, restricciones de integridad e inmutabilidad, migraciones y seed.

### Modified Capabilities

(ninguna)

## Impact

- Código nuevo: `backend/`, `tests/`, `pyproject.toml`, `widget/README.md`, `agent/README.md`.
- Dependencias nuevas: fastapi, uvicorn, sqlalchemy, alembic, psycopg, pydantic-settings; dev: pytest, ruff.
- Sin endpoints de negocio ni cambios de API pública. Sin impacto en la documentación de la Entrega 1.

## Fuera de alcance

- Endpoints `signature-requests`, `prepare`, `complete`, `signature-batches` (FIRDOC-23, FIRDOC-29).
- Motor PAdES, validación de confianza, proveedores de firma.
- Widget React (FIRDOC-30) y agente local (FIRDOC-21): solo se crean los directorios con README.
- Almacenamiento real de binarios: `storage_ref` es una referencia, sin implementación de object storage.
