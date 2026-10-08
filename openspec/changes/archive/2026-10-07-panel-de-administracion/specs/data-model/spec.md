## ADDED Requirements

### Requirement: Tabla de eventos de administración
La migración `0003` SHALL crear la tabla `admin_event` (`id`, `actor`, `action`, `detail` JSON, `created_at`) y SHALL rechazar `UPDATE` y `DELETE` sobre ella a nivel de base de datos en SQLite y PostgreSQL, sin modificar los triggers existentes. La migración SHALL ser reversible.

#### Scenario: Esquema
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** existe `admin_event` con sus triggers y los triggers anteriores siguen vigentes

#### Scenario: Inmutabilidad
- **WHEN** se intenta modificar o borrar una fila de `admin_event`
- **THEN** la base de datos lo rechaza

#### Scenario: Reversibilidad
- **WHEN** se ejecuta `alembic downgrade 0002`
- **THEN** `admin_event` y sus triggers desaparecen sin afectar el resto
