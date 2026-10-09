## Why

El almacén `database` (los PDF dentro de la base, tabla `stored_blob`) existe desde FIRDOC-31 y es la configuración recomendada para operar (`docs/database.md`, `docs/real-mode.md`), pero nadie lo usa en el día a día: el modo demostración fuerza `FIRMADOC_STORAGE_BACKEND=files` y deja los PDF en `data/demo/storage/`. La usuaria pidió que lo que se guarda en la demo quede dentro de la base, como en una instalación real. Implementa **FIRDOC-54** (épica FIRDOC-5).

## What Changes

- `python -m firmadoc.demo` configura `FIRMADOC_STORAGE_BACKEND=database`: los PDF cargados, el estado intermedio de la firma y los PDF del seed quedan en `stored_blob` de `data/demo/firmadoc-demo.db`. No se crean archivos nuevos en `data/demo/storage/`.
- Al preparar el entorno, si en `data/demo/storage/` quedaron PDF de versiones anteriores a este cambio, la demo los copia a la base con la migración existente (`files-to-database`), que verifica cada PDF contra el hash de su versión y no borra los archivos. Si alguna versión no se puede migrar, la demo informa el problema y no arranca. Es idempotente: en los arranques siguientes no copia nada.
- La migración entre almacenes omite, sin informarlo como problema, las versiones cuyo binario ya está en el destino y no existe en el origen (versiones creadas directamente en la base). Hoy las informa como «no se pudo leer del origen».
- La guía de arranque dice que los PDF están dentro de la base y cuántos se pasaron desde el disco, si hubo.
- Documentación (`docs/demo.md`, `README.md`, `docs/database.md`) alineada.
- El almacén por defecto del servidor fuera de la demo sigue siendo `files`: no cambia el comportamiento de instalaciones existentes.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `demo-mode`: el requisito «Entorno de demostración con un comando» pasa a guardar los PDF en la base; nuevo requisito «PDF de arranques anteriores pasan a la base».
- `database-storage`: el requisito «Migración entre almacenes» admite versiones que ya están en el destino y no en el origen (se omiten, no es un problema).

## Impact

- `backend/src/firmadoc/demo.py` (`prepare`, `DemoEnv`, `guide`), `backend/src/firmadoc/storage_migrate.py` (`_copy`).
- Tests: `tests/test_demo.py` (PDF en `stored_blob`, migración de un entorno con archivos, entorno roto), `tests/test_database_storage.py` (versión ya en destino sin origen).
- Docs: `docs/demo.md`, `README.md`, `docs/database.md`.
- Sin cambios en la API, el widget, el panel ni el esquema de la base (la tabla `stored_blob` y sus triggers ya existen en la migración 0006, también en SQLite).

## Fuera de alcance

- Cambiar el valor por defecto de `FIRMADOC_STORAGE_BACKEND` para el servidor fuera de la demo.
- Borrar `data/demo/storage/` después de migrar: queda como copia; `--reset` lo borra con todo lo demás.
- Correr la demo contra PostgreSQL.
