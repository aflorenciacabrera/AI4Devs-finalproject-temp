## Why

La demo (`python -m firmadoc.demo`) es la forma en que se muestra y se prueba Firmadoc, pero siempre corre sobre una SQLite en `data/demo/`. Para enseñar la instalación recomendada (PostgreSQL con los PDF en `stored_blob`, `docs/database.md`) hoy hay que abandonar la demo y armar a mano el servidor, sin token de prueba ni guía. La usuaria pidió correr la demo contra la base PostgreSQL del proyecto. Implementa **FIRDOC-55** (épica FIRDOC-5).

## What Changes

- Nueva opción `--database-url <url>` de `python -m firmadoc.demo`. Con ella la demo usa esa base (migraciones hasta la última, seed idempotente, PDF en `stored_blob` de esa base) y conserva todo lo demás: carpeta `data/demo/` con secretos, token de prueba, directorio de confianza y certificado de «Firma propia»; guía; `FIRMADOC_PUBLIC_BASE_URL`. Sin la opción, nada cambia (SQLite en `data/demo/`).
- La guía muestra a qué base está conectada, sin la contraseña.
- `--reset` sigue borrando solo `data/demo/`: la base externa no se toca. La guía, con una base externa, dice cómo empezar de cero (`docker compose down -v` para la del proyecto).
- Si la base externa tiene versiones cuyo PDF no está ni en `stored_blob` ni en `data/demo/storage/`, la demo no arranca e indica cómo migrarlos (`storage_migrate` con `FIRMADOC_STORAGE_DIR`) o recrear la base. Es el mismo control que con SQLite, con un mensaje que no sugiere `--reset` porque no resolvería nada.
- Una URL que SQLAlchemy no entiende es un error claro antes de tocar el disco.
- Documentación: `docs/demo.md`, `docs/database.md`, `README.md`.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `demo-mode`: nuevo requisito «Demo sobre una base externa» (`--database-url`); el requisito «PDF de arranques anteriores pasan a la base» distingue el mensaje de error según la base sea la propia o externa.

## Impact

- `backend/src/firmadoc/demo.py` (`prepare`, `DemoEnv`, `guide`, `main`).
- Tests: `tests/test_demo.py` (SQLite alternativa por `--database-url`, URL inválida, guía sin contraseña; contra PostgreSQL real con `FIRMADOC_TEST_PG_URL`, como el resto de la suite).
- Docs: `docs/demo.md`, `docs/database.md`, `README.md`.
- Sin cambios en el servidor, la API, el widget, el panel ni el esquema.

## Fuera de alcance

- Levantar PostgreSQL desde la demo (sigue siendo `docker compose up -d postgres`).
- Borrar o recrear la base externa desde la demo.
- Modo real: la demo sigue negándose con `FIRMADOC_REAL_MODE=true`.
