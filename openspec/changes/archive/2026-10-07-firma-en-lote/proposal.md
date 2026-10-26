## Why

Un funcionario con token suele firmar decenas de documentos seguidos. Hoy cada documento exige su propia solicitud y, con el agente, su propio ingreso de PIN. El agente local ya firma varios hashes en una sola llamada con un único PIN (`POST /sign` con N hashes), pero el servidor no tiene forma de preparar ni completar N documentos juntos. El modelo ya tiene `SignatureBatch` y `SignatureRequest.batch_id`, sin uso.

Backlog: FIRDOC-22 (HU6, firma en lote).

## What Changes

- **API de lotes** (`signature-batches`), autenticada con la API key del integrador:
  - `POST /api/v1/signature-batches` crea un lote con N documentos, un firmante y un proveedor comunes. Es atómico: si un documento es inválido no se crea ninguno.
  - `POST /api/v1/signature-batches/{id}/prepare` prepara las N solicitudes con el mismo certificado y devuelve N desafíos (uno por documento).
  - `POST /api/v1/signature-batches/{id}/complete` recibe N firmas, completa cada solicitud y devuelve el resultado por documento. Un documento que falla no impide que los demás se firmen.
  - `GET /api/v1/signature-batches/{id}` desglosa el estado de cada solicitud.
- **Estado del lote** derivado del estado de sus solicitudes: `pending`, `signing`, `completed`, `partial_failure`, `failed`.
- **Cada documento conserva todo su mecanismo**: su propio desafío de un solo uso, su propia `DocumentVersion` inmutable, su propia auditoría y su propio webhook (si el lote lleva `callback_url`). El lote solo agrupa.
- Eventos de auditoría del lote (`batch_created`, `batch_prepared`, `batch_completed`) sobre `audit_event.batch_id`.
- Límite configurable de documentos por lote (`FIRMADOC_MAX_BATCH_SIZE`, 50 por defecto).

## Capabilities

### New Capabilities

- `signature-batches`: creación, preparación, completado y consulta de lotes de firma.

### Modified Capabilities

- Ninguna (los requisitos de `signature-requests` no cambian: el lote reutiliza su flujo).

## Impact

- Servidor: `services/signature_batch.py`, rutas y esquemas nuevos, y una pequeña refactorización de `create_request` para poder crear solicitudes sin confirmar la transacción. Sin migración: las tablas ya existen.
- Variable de entorno nueva: `FIRMADOC_MAX_BATCH_SIZE`.
- Documentación: `docs/signature-batches.md`.

## Fuera de alcance

- Pantallas del widget para lotes (el widget actual es de una solicitud). El contrato con el agente ya admite N hashes; el uso desde un navegador queda para un cambio posterior del widget.
- Lotes con el proveedor `firmar` (no habilitado).
- Reintentar solo los documentos fallidos de un lote: se crea otro lote con ellos.
