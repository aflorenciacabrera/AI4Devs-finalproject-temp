# Base de datos de Firmadoc (PostgreSQL)

Toda la información de Firmadoc vive en una sola base: solicitudes, versiones de documentos, auditoría, desafíos,
webhooks, administración **y los PDF** (tabla `stored_blob`, almacén `database`).

El modo demostración (`python -m firmadoc.demo`) usa el mismo almacén sobre SQLite: los PDF de `data/demo/` están en
`stored_blob` de `data/demo/firmadoc-demo.db` (se consultan igual, por ejemplo con DBeaver y el driver SQLite). Para
verla sobre esta base: `python -m firmadoc.demo --database-url postgresql+psycopg://firmadoc:firmadoc@localhost:5432/firmadoc`
(`demo.md`, «Con PostgreSQL»); el seed crea el integrador de demostración, así que no se usa con una base de trabajo.

> Las credenciales de este documento y de `docker-compose.yml` son **solo de desarrollo**. En un despliegue real se
> definen con las variables `FIRMADOC_DB_USER`, `FIRMADOC_DB_PASSWORD` y `FIRMADOC_DB_NAME` (o las de la base
> institucional) y no se versionan.

## Levantar la base

```bash
docker compose up -d postgres          # PostgreSQL 16, datos persistentes en el volumen firmadoc-pgdata
docker compose ps                      # debe figurar "healthy"
```

Configurar el servidor (`.env`):

```
FIRMADOC_DATABASE_URL=postgresql+psycopg://firmadoc:firmadoc@localhost:5432/firmadoc
FIRMADOC_STORAGE_BACKEND=database      # los PDF dentro de la base (por defecto: files, en disco)
```

Crear el esquema y cargar los datos de demostración:

```bash
alembic upgrade head                   # tablas, restricciones y triggers de inmutabilidad
python -m firmadoc.seed                # sistema integrador de demostración (API key: firmadoc-demo-key)
uvicorn firmadoc.main:app
```

`docker compose down` conserva los datos; `docker compose down -v` **los borra**.

## Conectar con DBeaver

Nueva conexión → PostgreSQL:

| Campo | Valor (desarrollo) |
|---|---|
| Host | `localhost` |
| Puerto | `5432` |
| Base de datos | `firmadoc` |
| Usuario | `firmadoc` |
| Contraseña | `firmadoc` |
| URL JDBC | `jdbc:postgresql://localhost:5432/firmadoc` |

Si DBeaver pide el driver, aceptar la descarga. Las tablas están en el esquema `public`.

## Qué hay en la base

| Tabla | Contenido |
|---|---|
| `integrating_system` | Sistemas integradores (la API key se guarda solo como hash; el secreto de webhook) |
| `signer`, `certificate` | Firmantes y datos públicos de los certificados usados |
| `document`, `document_version` | Documentos y sus versiones (inmutables: no admiten `UPDATE` ni `DELETE`) |
| `stored_blob` | **Los PDF** (`content`), con tamaño y SHA-256; inmutables, salvo el estado intermedio `prepared/…` |
| `signature_request`, `signature_batch`, `signing_challenge` | Solicitudes, lotes y desafíos de firma (un solo uso) |
| `audit_event` | Auditoría append-only |
| `webhook_delivery` | Entregas de webhook y sus intentos |
| `admin_event` | Acciones de administración (append-only) |
| `alembic_version` | Versión del esquema |

Consultas útiles:

```sql
-- PDF guardados, con su versión
SELECT d.external_document_id, v.version_number, v.origin, b.size, b.ref
FROM document_version v JOIN document d ON d.id = v.document_id
JOIN stored_blob b ON b.ref = v.storage_ref ORDER BY v.created_at;

-- Auditoría de una solicitud
SELECT event_type, payload, created_at FROM audit_event ORDER BY created_at DESC LIMIT 20;
```

Las protecciones de inmutabilidad valen también desde DBeaver: modificar o borrar una versión, un evento de
auditoría o un PDF falla con un error explícito.

## Pasar de archivos a la base

Con instalaciones que guardaban los PDF como archivos (`FIRMADOC_STORAGE_BACKEND=files`):

```bash
# con el servicio detenido
python -m firmadoc.storage_migrate files-to-database   # verifica cada PDF contra el hash de su versión
# luego: FIRMADOC_STORAGE_BACKEND=database
```

Es idempotente, informa los problemas (archivo ausente, corrupto o con contenido distinto en el destino) y **no
borra los archivos**: eso lo decide quien opera, después de verificar. `database-to-files` hace lo inverso.

## Migrar a la base institucional

1. Obtener de sistemas una base PostgreSQL vacía (esquema, usuario y permisos de DDL para las migraciones).
2. Apuntar `FIRMADOC_DATABASE_URL` a esa base y ejecutar `alembic upgrade head`.
3. Si hay datos que conservar:
   - **Desde otra base PostgreSQL de Firmadoc**: volcado y restauración (`pg_dump -Fc` y `pg_restore`) de toda
     la base; incluye los PDF, porque están en la base.
   - **Desde archivos**: `python -m firmadoc.storage_migrate files-to-database` (los datos relacionales se
     migran con el volcado).
4. Cargar el seed solo en entornos de demostración (`python -m firmadoc.seed`).
5. Crear los integradores reales con `python -m firmadoc.integrators create` y configurar el administrador
   (`docs/admin.md`).

Recomendaciones para la base institucional: cifrado del volumen o de la columna `stored_blob.content` (los
documentos pueden ser sensibles), copias de seguridad que incluyan todas las tablas, usuario de aplicación sin
permisos de DDL en producción (las migraciones se ejecutan con otro usuario) y TLS en la conexión.

## Pruebas contra PostgreSQL

```bash
docker compose up -d postgres
docker compose exec postgres psql -U firmadoc -d postgres -c "CREATE DATABASE firmadoc_test"
FIRMADOC_TEST_PG_URL=postgresql+psycopg://firmadoc:firmadoc@localhost:5432/firmadoc_test pytest
```

La suite **recrea el esquema `public`** de esa base en cada prueba: usar siempre una base descartable
(`firmadoc_test`), nunca la base de trabajo.
