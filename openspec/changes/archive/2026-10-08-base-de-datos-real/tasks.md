## 1. Esquema y almacén

- [x] 1.1 Modelo `StoredBlob` y migración `0006` reversible con triggers (SQLite y PostgreSQL) y su prueba
- [x] 1.2 `DatabaseStorage` (guardar sin sobrescribir, leer verificando el hash, descartar solo `prepared/`, validación de referencias)
- [x] 1.3 `storage_backend` en `Settings` (validado) y selección del almacén en `get_storage` con la sesión del pedido
- [x] 1.4 `python -m firmadoc.storage_migrate` (`files-to-database` y `database-to-files`)

## 2. Despliegue

- [x] 2.1 `docker-compose.yml`: volumen, healthcheck, variables y puerto solo local; `.env.example`
- [x] 2.2 `docs/database.md` (DBeaver, comandos, tablas, migración a la base institucional) y enlace desde `backend/README.md`

## 3. Pruebas

- [x] 3.1 `DatabaseStorage`: ida y vuelta, repetido, inexistente, referencias inválidas, hash alterado, triggers (UPDATE/DELETE) y descarte de `prepared/`
- [x] 3.2 Atomicidad: una operación revertida no deja binario
- [x] 3.3 Flujo completo con el almacén `database` (firma local, token, lote, firma remota, verificación, descarga y webhooks) sin directorio de archivos
- [x] 3.4 Migración entre almacenes: completa, repetida, archivo corrupto o ausente, inversa
- [x] 3.5 Ejecutar la suite completa contra PostgreSQL real y corregir lo que aparezca

## 4. Base real y cierre

- [x] 4.1 Levantar PostgreSQL con Docker, migrar, cargar el seed y dejar un documento firmado de ejemplo guardado en la base; comprobar con `psql` y con una conexión como la de DBeaver
- [x] 4.2 Ejecutar `pytest` (SQLite y PostgreSQL) y `ruff check` sin errores
