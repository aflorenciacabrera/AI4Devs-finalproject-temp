# database-deployment Specification

## Purpose
TBD - created by archiving change base-de-datos-real. Update Purpose after archive.

## Requirements

### Requirement: PostgreSQL con Docker Compose
`docker-compose.yml` SHALL definir un servicio PostgreSQL 16 con volumen con nombre (los datos persisten tras `docker compose down`), `healthcheck` con `pg_isready`, usuario, clave y base configurables por variables de entorno con valores de desarrollo por defecto, y el puerto publicado solo en `127.0.0.1`.

#### Scenario: Persistencia
- **WHEN** se detiene y se vuelve a levantar el servicio
- **THEN** los datos siguen presentes

#### Scenario: Salud
- **WHEN** la base aún no acepta conexiones
- **THEN** el servicio figura como no saludable hasta que las acepta

### Requirement: Base migrada y con datos de demostración
Con la URL de PostgreSQL configurada, `alembic upgrade head` SHALL crear el esquema completo (incluidos los triggers de inmutabilidad) y `python -m firmadoc.seed` SHALL cargar los datos de demostración, de forma repetible sin errores ni duplicados.

#### Scenario: Esquema en PostgreSQL
- **WHEN** se migra una base vacía
- **THEN** existen todas las tablas y las operaciones prohibidas (modificar versiones, auditoría o binarios) fallan

#### Scenario: Seed repetido
- **WHEN** se ejecuta el seed dos veces
- **THEN** la segunda lo informa como ya aplicado

### Requirement: Guía de conexión y de migración
`docs/database.md` SHALL documentar los datos de conexión para DBeaver (host, puerto, base, usuario y clave de desarrollo), los comandos para levantar, migrar, cargar el seed y configurar el servidor, qué tablas contiene la base (incluida la de los PDF), y los pasos para migrar a la base institucional (nueva URL, migraciones, migración de binarios o volcado), aclarando que las credenciales del compose son solo de desarrollo.

#### Scenario: Conexión
- **WHEN** se siguen los pasos de la guía
- **THEN** DBeaver se conecta y muestra las tablas, con los PDF en `stored_blob`

### Requirement: Pruebas contra PostgreSQL
La suite SHALL poder ejecutarse contra PostgreSQL real definiendo `FIRMADOC_TEST_PG_URL`, y SHALL incluir el flujo completo de firma (crear, preparar, completar, verificar y descargar) con el almacén `database` en SQLite y en PostgreSQL.

#### Scenario: Suite en PostgreSQL
- **WHEN** se ejecuta la suite con `FIRMADOC_TEST_PG_URL`
- **THEN** las variantes PostgreSQL se ejecutan y pasan
