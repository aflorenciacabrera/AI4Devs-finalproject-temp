## ADDED Requirements

### Requirement: Tabla de binarios
La migración `0006` SHALL crear `stored_blob` (`ref` clave primaria, `content` binario, `size`, `sha256`, `created_at`) y sus triggers (rechazo de `UPDATE` y de `DELETE` salvo referencias `prepared/…`) en SQLite y PostgreSQL, sin modificar los triggers ni los datos existentes y de forma reversible.

#### Scenario: Migración
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** existe `stored_blob` con sus triggers y los anteriores siguen vigentes

#### Scenario: Reversibilidad
- **WHEN** se ejecuta `alembic downgrade 0005`
- **THEN** `stored_blob` y sus triggers desaparecen sin afectar el resto
