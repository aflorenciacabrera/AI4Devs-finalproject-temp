## ADDED Requirements

### Requirement: Operación remota de una solicitud
La migración `0004` SHALL agregar `signature_request.remote_operation_id` (texto, nulo, único) para ubicar la solicitud a la que corresponde un callback del servicio de firma remota, sin modificar los triggers existentes y de forma reversible.

#### Scenario: Migración
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** existe `remote_operation_id` con índice único y los datos previos se conservan

#### Scenario: Unicidad
- **WHEN** dos solicitudes intentan usar el mismo `remote_operation_id`
- **THEN** la base de datos rechaza la segunda

#### Scenario: Reversibilidad
- **WHEN** se ejecuta `alembic downgrade 0003`
- **THEN** la columna y su índice desaparecen sin afectar el resto
