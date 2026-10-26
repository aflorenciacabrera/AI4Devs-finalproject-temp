## Context

Ver `proposal.md`. `demo.prepare()` fija las variables de entorno del proceso, corre Alembic, abre una sesión y carga el seed con `LocalFileStorage(data/demo/storage)`. El servidor elige el almacén en `api/deps.get_storage` según `FIRMADOC_STORAGE_BACKEND`; `DatabaseStorage` ya está probado de punta a punta (`tests/test_database_storage.py`), también en SQLite (triggers de la migración 0006). `storage_migrate._copy` recorre las versiones y, para cada una, lee el origen, verifica el hash y recién después mira el destino: una versión guardada directamente en la base (sin archivo) se informa como problema.

La usuaria tiene un `data/demo/` con documentos firmados con el token real cuyos PDF están en disco: no se pueden perder ni exigir `--reset`.

## Goals / Non-Goals

**Goals:** la demo guarda todo en la base; un entorno anterior sigue funcionando sin intervención; ningún archivo se borra automáticamente.

**Non-Goals:** cambiar el valor por defecto del servidor; PostgreSQL en la demo; limpiar `data/demo/storage/`.

## Decisions

1. **`FIRMADOC_STORAGE_BACKEND=database` fijo en la demo, sin opción para volver a `files`.** `data/demo/` es un entorno descartable y la demo debe parecerse a la instalación recomendada. `FIRMADOC_STORAGE_DIR` sigue apuntando a `data/demo/storage` porque es el origen de la migración y porque el seed, el panel y los tests lo leen de la configuración; con el almacén `database` el servidor no lo usa.
2. **Migración al preparar, con la función existente.** `prepare()` llama a `storage_migrate.migrate(session, "files-to-database", storage_dir)` en la misma sesión que el seed, antes del seed (así el seed no interfiere y el informe cuenta solo lo anterior). Si `report.problems` no está vacío, `prepare` lanza `DemoError` con la lista: un entorno que no se puede migrar completo no debe arrancar a medias (el servidor fallaría al descargar esas versiones). Alternativa descartada: migrar solo si existe `data/demo/storage/`; es más frágil y la migración sin versiones en disco cuesta una consulta.
3. **`_copy` mira primero el destino.** Si la referencia ya está en el destino: con origen ausente se omite, con origen idéntico se omite, con origen distinto es conflicto. Si no está en el destino: origen ausente o corrupto es problema (igual que hoy). Así el seed y las versiones firmadas en la base no se informan como problemas y el comando manual conserva sus garantías. Se aplica a ambas direcciones.
4. **Seed con `DatabaseStorage(session)`.** `seed_demo` ya acepta cualquier `DocumentStorage`; `DatabaseStorage.save` solo hace `flush` y el seed hace `commit` al final: binarios y versiones del seed quedan en la misma transacción.
5. **Guía.** Línea «PDF: dentro de la base (`firmadoc-demo.db`, tabla `stored_blob`)» y, si `migrated > 0`, «Se copiaron N PDF de `data/demo/storage/` a la base; los archivos quedan como copia y se pueden borrar». `DemoEnv` gana `migrated: int = 0`.
6. **Sin `mkdir` de `storage/`.** Ya no se crea la carpeta en el primer arranque: su ausencia es la señal de que el entorno nació con este cambio.

## Risks / Trade-offs

- [Entornos antiguos con un PDF corrupto o borrado a mano no arrancan] → el mensaje lista cada versión afectada y sugiere `--reset`; es preferible a servir descargas rotas.
- [La base SQLite de la demo crece con los PDF] → es demostración; `--reset` la recrea. En PostgreSQL ya se documentó el cifrado y las copias de seguridad.
- [Otra sesión edita el widget (`serverClient.ts`, `clients.test.ts`) sin commitear] → este cambio no toca el widget; al commitear, `git add` por rutas.

## Migration Plan

Sin migración de esquema. Al arrancar la demo sobre un `data/demo/` existente, los PDF de disco pasan a la base automáticamente. Rollback: revertir el commit; los archivos siguen en `data/demo/storage/`, y los PDF creados mientras tanto en la base se pueden sacar con `python -m firmadoc.storage_migrate database-to-files` apuntando a la base de la demo.
