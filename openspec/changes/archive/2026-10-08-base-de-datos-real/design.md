## Context

`DocumentStorage` (guardar, leer, borrar el estado intermedio) tiene hoy una sola implementación, `LocalFileStorage`. El flujo guarda el binario **antes** de insertar la versión, así que una transacción fallida deja un archivo huérfano (la referencia incluye el id de la versión para no colisionar). La base ya garantiza la inmutabilidad de `document_version` con triggers; los binarios no tienen esa garantía.

## Goals / Non-Goals

**Goals:** todo en la base; binarios atómicos con su versión; inmutabilidad e integridad verificables; migración sin pérdida entre almacenes; una base real de desarrollo conectable con DBeaver y un camino claro hacia la base institucional.

**Non-Goals:** cifrado en reposo, backups, streaming (ver proposal).

## Decisions

1. **Tabla `stored_blob`** (`ref` clave primaria, `content` binario, `size`, `sha256`, `created_at`) y no columnas en `document_version`: `document_version` es inmutable y los binarios del estado intermedio (`prepared/…`) no son versiones; además mantiene la interfaz `DocumentStorage` intacta (se accede por `ref`, no por id de versión). Alternativa descartada: un campo bytea en `document_version` (acopla el almacén al modelo y obliga a tocar el flujo).
2. **El almacén usa la sesión del pedido**, no una conexión propia. Así el binario y la versión se confirman o se revierten **juntos**: desaparecen los huérfanos que hoy se toleran. También evita el bloqueo de SQLite (una segunda conexión de escritura mientras la sesión del pedido tiene una escritura abierta quedaría esperando). Costo: `DatabaseStorage` se construye por pedido (`get_storage` depende de `get_db`), lo que es barato.
3. **`save` hace `INSERT` y `flush`, nunca `UPDATE`.** Una referencia repetida es un error (`StorageError`), igual que el almacén de archivos (`open(..., "xb")`). El `flush` adelanta el error de duplicado al punto de la llamada.
4. **Inmutabilidad a nivel de base de datos**: triggers que rechazan todo `UPDATE` y rechazan `DELETE` salvo cuando `ref` empieza con `prepared/` (estado intermedio descartable tras completar). Es la misma garantía que ya tienen `document_version` y `audit_event`; un `DELETE` o `UPDATE` de un binario de versión falla aunque alguien entre a la base con DBeaver.
5. **Integridad al leer**: `read` recalcula el SHA-256 y lo compara con el guardado; si no coincide, `StorageError` (corrupción o alteración directa en la base). Es independiente del `document_hash` de la versión, que `verify` ya compara.
6. **El almacén se elige por configuración** (`FIRMADOC_STORAGE_BACKEND`, `files` por defecto) para no romper instalaciones existentes ni los cientos de pruebas actuales; las pruebas del flujo se repiten con `database`.
7. **Migración entre almacenes con una herramienta de línea de comandos**, idempotente (omite lo ya copiado y verifica que lo existente coincide), que valida cada binario de versión contra el `document_hash` registrado antes de copiarlo y **no borra el origen**: el borrado es una decisión posterior del operador. Para la base institucional el camino es: cambiar la URL, `alembic upgrade head`, `storage_migrate files-to-database` (si venían de archivos) o un volcado/restauración de PostgreSQL (si venían de otra instancia).
8. **PostgreSQL con Docker Compose**: imagen `postgres:16`, volumen con nombre (los datos sobreviven a `down`), `healthcheck` con `pg_isready`, usuario/clave/base por variables con valores de desarrollo por defecto, puerto 5432 solo en `127.0.0.1`. Los valores por defecto son **solo de desarrollo** y la guía lo dice.
9. **Las pruebas pasan a correr también contra PostgreSQL** (la variable `FIRMADOC_TEST_PG_URL` ya está prevista y el CI la define): es la primera vez que se ejecutan localmente las variantes PostgreSQL, y se corrigen las diferencias que aparezcan.

## Risks / Trade-offs

- Los PDF dentro de la base agrandan la base y su copia de seguridad; es la contrapartida buscada (todo junto) y se mitiga con el tamaño máximo por documento. Con PostgreSQL los `bytea` grandes se almacenan fuera de línea (TOAST), sin degradar las consultas sobre las demás columnas.
- Cargar un documento entero en memoria al leer (como hoy con archivos); aceptable con el límite de 20 MB.
- Con `files`, los huérfanos siguen siendo posibles (sin cambio); el cambio los elimina solo con `database`.
