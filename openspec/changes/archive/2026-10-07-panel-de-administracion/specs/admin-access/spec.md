## ADDED Requirements

### Requirement: Autenticación de administración
Las rutas bajo `/api/v1/admin` SHALL exigir `Authorization: Bearer <token>` igual a `FIRMADOC_ADMIN_TOKEN`, comparado en tiempo constante. Si el token de administración no está configurado, esas rutas y la página `/admin/api` SHALL responder `404`. Una API key de integrador SHALL NOT servir para administrar. `FIRMADOC_ADMIN_TOKEN` SHALL tener al menos 32 caracteres.

#### Scenario: Token correcto
- **WHEN** se llama con el token de administración
- **THEN** la ruta responde normalmente

#### Scenario: Token incorrecto o ausente
- **WHEN** falta la cabecera, el esquema no es `Bearer` o el token es otro
- **THEN** responde `401` sin indicar qué falló

#### Scenario: API key de integrador
- **WHEN** se usa una API key de integrador como token de administración
- **THEN** responde `401`

#### Scenario: Administración deshabilitada
- **WHEN** no hay `FIRMADOC_ADMIN_TOKEN` configurado
- **THEN** toda ruta de administración responde `404`

#### Scenario: Token demasiado corto
- **WHEN** el token configurado tiene menos de 32 caracteres
- **THEN** la configuración se rechaza al cargarse

### Requirement: Registro inmutable de acciones de administración
Toda acción de administración que modifique datos o configuración (reenviar un webhook, agregar o quitar un ancla de confianza, rotar el certificado propio) SHALL registrar un `admin_event` con el actor, la acción, el detalle y la fecha, en la misma operación. `admin_event` SHALL rechazar `UPDATE` y `DELETE` a nivel de base de datos. `GET /api/v1/admin/events` SHALL listar los eventos, del más reciente al más antiguo, con paginación.

#### Scenario: Acción registrada
- **WHEN** se agrega un ancla de confianza
- **THEN** existe un `admin_event` con la acción, la huella del ancla y la fecha

#### Scenario: Lecturas no se registran
- **WHEN** solo se consultan listados
- **THEN** no se crean `admin_event`

#### Scenario: Inmutabilidad
- **WHEN** se intenta modificar o borrar un `admin_event`
- **THEN** la base de datos lo rechaza
