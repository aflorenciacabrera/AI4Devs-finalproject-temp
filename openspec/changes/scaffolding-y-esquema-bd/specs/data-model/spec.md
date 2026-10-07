## ADDED Requirements

### Requirement: Esquema inicial completo
La migración inicial de Alembic SHALL crear las tablas de `IntegratingSystem`, `Document`, `DocumentVersion`, `SignatureRequest`, `SigningChallenge`, `SignatureBatch`, `Signer`, `Certificate`, `AuditEvent` y `WebhookDelivery` con los campos, tipos, enums y claves foráneas de la sección 3 del README.

#### Scenario: Migración desde cero
- **WHEN** se ejecuta `alembic upgrade head` sobre una base vacía
- **THEN** existen las 10 tablas con sus restricciones

#### Scenario: Migración reversible
- **WHEN** se ejecuta `alembic downgrade base` tras el upgrade
- **THEN** la base queda sin tablas de Firmadoc

### Requirement: Versiones de documento inmutables
La tabla `document_version` SHALL rechazar `UPDATE` y `DELETE` a nivel de base de datos, y SHALL tener un índice único sobre `(document_id, version_number)`.

#### Scenario: Intento de modificar una versión
- **WHEN** se ejecuta `UPDATE` o `DELETE` sobre una fila de `document_version`
- **THEN** la base de datos lo rechaza con un error explícito

#### Scenario: Número de versión duplicado
- **WHEN** se inserta una segunda versión con el mismo `(document_id, version_number)`
- **THEN** la inserción falla por violación de unicidad

### Requirement: Versión vigente sin pisar versiones
`Document.current_version_id` SHALL poder actualizarse para apuntar a una nueva versión sin modificar ninguna fila de `document_version`.

#### Scenario: Nueva versión vigente
- **WHEN** se inserta una versión nueva y se actualiza `current_version_id`
- **THEN** la versión anterior permanece intacta y deja de ser la vigente

### Requirement: Auditoría append-only
La tabla `audit_event` SHALL rechazar `UPDATE` y `DELETE` a nivel de base de datos y SHALL exigir exactamente uno de `signature_request_id` o `batch_id`.

#### Scenario: Evento sin referencia
- **WHEN** se inserta un evento sin `signature_request_id` ni `batch_id`
- **THEN** la inserción falla por la restricción de verificación

#### Scenario: Evento con ambas referencias
- **WHEN** se inserta un evento con ambos campos
- **THEN** la inserción falla por la restricción de verificación

### Requirement: Desafíos de un solo uso
`SigningChallenge.consumed_at` SHALL poder establecerse una única vez; una vez no nulo, la base de datos SHALL rechazar cualquier cambio posterior de la fila.

#### Scenario: Reutilización de un desafío
- **WHEN** se intenta modificar `consumed_at` de un desafío ya consumido
- **THEN** la base de datos lo rechaza

### Requirement: Unicidad de credenciales y certificados
`IntegratingSystem.api_key_hash` y `Certificate.serial_number` SHALL ser únicos y no nulos, y la API key SHALL almacenarse únicamente como hash.

#### Scenario: Serial duplicado
- **WHEN** se inserta un certificado con un `serial_number` existente
- **THEN** la inserción falla por violación de unicidad

### Requirement: Seed de demostración
El proyecto SHALL proveer un script de seed idempotente que cree un sistema integrador de prueba, un documento con dos versiones (`uploaded` y `signed`) y un certificado demo.

#### Scenario: Seed repetido
- **WHEN** el script de seed se ejecuta dos veces
- **THEN** no duplica datos ni falla
