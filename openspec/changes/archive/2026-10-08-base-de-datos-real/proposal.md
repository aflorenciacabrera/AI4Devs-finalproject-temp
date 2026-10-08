## Why

Hasta ahora Firmadoc corre sobre SQLite y guarda los PDF como archivos en disco (`data/storage`). Eso sirve para desarrollar, pero no para operar ni para auditar: los binarios quedan fuera de la base (sin transacción común con las versiones, sin las mismas garantías de inmutabilidad, sin copia de seguridad unificada) y no hay una base a la que conectarse con una herramienta como DBeaver para ver todo junto. Además, el destino es migrar a **la base institucional** que se defina, y para eso conviene que **todo** (datos y documentos) viva en la base y que el cambio sea cuestión de apuntar a otra conexión.

Backlog: tarea nueva de Jira (base de datos real y documentos en la base).

## What Changes

- **Almacenamiento en la base** (`database-storage`): una implementación `DatabaseStorage` de la interfaz `DocumentStorage` guarda cada PDF en la tabla `stored_blob` (bytea/BLOB), **en la misma transacción** que la versión que lo referencia (adiós a los binarios huérfanos), con su SHA-256, que se **verifica al leer**. A nivel de base de datos, los binarios de versiones son **append-only** (no admiten `UPDATE` ni `DELETE`); solo el estado intermedio de una firma (`prepared/…`) es descartable. Se elige con `FIRMADOC_STORAGE_BACKEND=files|database` (por defecto `files`, sin cambio para quien ya lo usa).
- **Migración entre almacenes** (`database-storage`): `python -m firmadoc.storage_migrate files-to-database` (y la inversa) copia los binarios existentes, verifica cada uno contra el hash registrado de su versión, es idempotente y no borra el origen.
- **Base real y despliegue** (`database-deployment`): PostgreSQL 16 con Docker Compose (volumen persistente, comprobación de salud, credenciales por variables), migrada con Alembic, con el seed de demostración aplicado, y la guía `docs/database.md` con los datos de conexión para DBeaver y los pasos para migrar a la base institucional (cambiar la URL, `alembic upgrade head`, `storage_migrate`).
- **PostgreSQL en las pruebas**: la suite se ejecuta contra PostgreSQL real además de SQLite (hasta ahora las variantes PostgreSQL se omitían); incluye el flujo completo de firma con los documentos en la base.
- Migración `0006`: `stored_blob` con sus triggers de inmutabilidad (SQLite y PostgreSQL).

## Capabilities

### New Capabilities

- `database-storage`: documentos en la base, integridad, inmutabilidad y migración entre almacenes.
- `database-deployment`: PostgreSQL con Docker, datos de conexión y migración a la base institucional.

### Modified Capabilities

- `data-model`: tabla `stored_blob`.

## Impact

- Servidor: `storage.py` (`DatabaseStorage`), `models.py` (`StoredBlob`), `api/deps.py` (el almacén se elige por configuración y usa la sesión del pedido), `storage_migrate.py`, `config.py`, migración `0006`.
- Infraestructura: `docker-compose.yml` (volumen, healthcheck, variables), `.env.example`.
- Documentación: `docs/database.md`; `backend/README.md`.

## Fuera de alcance

- Cifrado de los documentos en reposo en la base (se recomienda el cifrado a nivel de columna o de volumen de la base institucional) y copias de seguridad programadas: son del despliegue de cada base.
- Streaming de documentos muy grandes (el tamaño máximo por documento sigue siendo 20 MB y se leen enteros en memoria, como hasta ahora).
- Cambiar de almacén "en caliente" con tráfico: se migra con el servicio detenido.
- Credenciales de producción: las del `docker-compose.yml` son solo de desarrollo.
