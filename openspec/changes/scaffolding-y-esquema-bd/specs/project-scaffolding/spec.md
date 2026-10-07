## ADDED Requirements

### Requirement: Estructura del repositorio
El repositorio SHALL contener los directorios `backend/`, `widget/`, `agent/` y `tests/`, cada componente sin código de negocio fuera de `backend/` con un README que describa su propósito y el ticket que lo implementa.

#### Scenario: Directorios presentes
- **WHEN** se clona el repositorio
- **THEN** existen `backend/`, `widget/README.md`, `agent/README.md` y `tests/`

### Requirement: Arranque de la aplicación
La aplicación FastAPI SHALL exponer `GET /health` que responda `200` con `{"status": "ok"}` sin requerir autenticación ni base de datos.

#### Scenario: Health check
- **WHEN** se invoca `GET /health`
- **THEN** la respuesta es `200` con `{"status": "ok"}`

### Requirement: Configuración por entorno
La URL de la base de datos SHALL leerse de la variable de entorno `FIRMADOC_DATABASE_URL`, con SQLite local como valor por defecto de desarrollo, y ningún secreto SHALL estar versionado.

#### Scenario: Base de datos configurable
- **WHEN** `FIRMADOC_DATABASE_URL` apunta a PostgreSQL
- **THEN** la aplicación y Alembic usan esa base de datos

### Requirement: Herramientas de desarrollo
El proyecto SHALL poder instalarse con un único comando y SHALL ejecutar tests con `pytest` y lint con `ruff`.

#### Scenario: Tests ejecutables
- **WHEN** se ejecuta `pytest` en un entorno con las dependencias de desarrollo
- **THEN** la suite corre y finaliza sin errores de importación
