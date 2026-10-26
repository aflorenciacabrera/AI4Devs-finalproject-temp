## ADDED Requirements

### Requirement: Proveedores permitidos de una solicitud
La migración `0005` SHALL agregar `signature_request.allowed_providers` (texto, nulo) con los proveedores permitidos separados por coma, sin modificar los triggers ni los datos existentes y de forma reversible. Un valor nulo SHALL significar que la solicitud admite únicamente su `provider`.

#### Scenario: Migración
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** existe `allowed_providers`, nulo en las solicitudes previas, y sus datos se conservan

#### Scenario: Reversibilidad
- **WHEN** se ejecuta `alembic downgrade 0004`
- **THEN** la columna desaparece sin afectar el resto
