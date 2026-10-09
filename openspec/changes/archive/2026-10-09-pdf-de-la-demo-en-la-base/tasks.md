## 1. Migración entre almacenes

- [x] 1.1 `storage_migrate._copy`: mirar primero el destino; versión ya en destino sin origen se omite; conservar problema y conflicto como hoy. Test en `tests/test_database_storage.py` (versión creada en la base, sin archivo, no es problema; repetir no falla).

## 2. Demo con los PDF en la base

- [x] 2.1 `demo.prepare`: `FIRMADOC_STORAGE_BACKEND=database`; no crear `storage/`; antes del seed, `migrate(session, "files-to-database", storage_dir)`; con problemas, `DemoError` que lista cada versión y sugiere `--reset`; `DemoEnv.migrated`; seed con `DatabaseStorage(session)`.
- [x] 2.2 `demo.guide`: línea «PDF: dentro de la base» y, si hubo copia, cuántos PDF se copiaron y que los archivos quedan en `data/demo/storage/`.
- [x] 2.3 `tests/test_demo.py`: primer arranque sin PDF en disco y con PDF del seed en `stored_blob`; firma desde el panel deja v1 y v2 en `stored_blob` sin archivos; entorno anterior con PDF en disco se migra (guía con la cantidad, archivos intactos, descarga correcta, segundo arranque sin copia); PDF ausente o corrupto → `DemoError` sin arrancar.
- [x] 2.4 `pytest tests -q --ignore=tests/e2e` y `ruff check` en verde.

## 3. Documentación

- [x] 3.1 `docs/demo.md` (tabla «Qué crea»: PDF en la base; `storage/` solo en entornos anteriores), `README.md` (línea del modo demo y «Cómo correr todo en limpio»), `docs/database.md` (la demo también guarda los PDF en `stored_blob`, en SQLite).

## 4. Verificación

- [x] 4.1 Arrancar `python -m firmadoc.demo` sobre el `data/demo/` actual: la guía informa los PDF copiados, los documentos firmados con el token se descargan, y un PDF nuevo cargado desde el panel aparece en `stored_blob` y no en `data/demo/storage/`.
