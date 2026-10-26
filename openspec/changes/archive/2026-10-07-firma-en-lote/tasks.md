## 1. Servidor

- [x] 1.1 Agregar `max_batch_size` a `Settings` y `.env.example`
- [x] 1.2 Refactorizar `create_request` con el parámetro `commit` (por defecto `True`) sin cambiar su comportamiento actual
- [x] 1.3 Implementar `services/signature_batch.py`: crear (atómico), preparar, completar (fallos parciales), consultar y la función pura de estado
- [x] 1.4 Esquemas y rutas `/api/v1/signature-batches` (crear, prepare, complete, GET)
- [x] 1.5 Eventos de auditoría del lote sobre `batch_id`

## 2. Pruebas

- [x] 2.1 Función de estado (todas las combinaciones)
- [x] 2.2 Lote `local` de punta a punta: tres documentos, versiones, auditoría, descarga y verificación de las firmas
- [x] 2.3 Lote `token` con el agente simulado: un hash por documento, un solo `session_ref`
- [x] 2.4 Fallo parcial (firma inválida), firma faltante, lote ya completado y lote sin preparar
- [x] 2.5 Atomicidad de la creación, límites de cantidad, `document_id` existente, API key y aislamiento entre integradores
- [x] 2.6 Webhooks: una entrega por documento firmado

## 3. Documentación y cierre

- [x] 3.1 Escribir `docs/signature-batches.md` y enlazarlo desde `backend/README.md`
- [x] 3.2 Ejecutar `pytest` y `ruff check` sin errores
