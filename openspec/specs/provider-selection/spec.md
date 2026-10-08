# provider-selection Specification

## Purpose
TBD - created by archiving change eleccion-de-proveedor-en-el-widget. Update Purpose after archive.

## Requirements

### Requirement: Proveedores permitidos de una solicitud
`POST /api/v1/signature-requests` SHALL aceptar `allowed_providers` (lista de proveedores) con los métodos que se ofrecen a la persona; cada uno SHALL ser un proveedor conocido y habilitado, sin repetidos, e incluir al `provider` indicado, que es el proveedor inicial. Sin `allowed_providers` la solicitud SHALL admitir únicamente `provider`.

#### Scenario: Varios métodos
- **WHEN** se crea una solicitud con `provider: token` y `allowed_providers: [token, local]`
- **THEN** responde `201` y la solicitud ofrece ambos métodos

#### Scenario: Lista sin el proveedor inicial
- **WHEN** `allowed_providers` no incluye a `provider`
- **THEN** responde `422` y no se crea nada

#### Scenario: Proveedor no habilitado
- **WHEN** la lista incluye `firmar` y el servicio remoto no está configurado
- **THEN** responde `422`

#### Scenario: Repetidos o desconocidos
- **WHEN** la lista repite un proveedor o incluye uno inexistente
- **THEN** responde `422`

### Requirement: Contexto del widget con los métodos disponibles
`GET /api/v1/widget/requests/{id}` SHALL incluir `allowed_providers`: los permitidos de la solicitud que estén habilitados en el servidor, o solo `provider` si la solicitud no definió una lista.

#### Scenario: Solicitud de un solo método
- **WHEN** la solicitud no tiene `allowed_providers`
- **THEN** el contexto informa `allowed_providers: [provider]`

#### Scenario: Método deshabilitado después
- **WHEN** un método permitido dejó de estar habilitado en el servidor
- **THEN** no figura en `allowed_providers` del contexto

### Requirement: Elegir el método desde el widget
`POST /api/v1/widget/requests/{id}/provider` con `{"provider": "<método>"}` SHALL fijar el proveedor de la solicitud si está `pending` y el método figura entre los disponibles, SHALL registrar el evento de auditoría `provider_selected` con el proveedor anterior y el nuevo, y SHALL responder `200` con el contexto actualizado. Elegir el proveedor ya activo SHALL ser válido y no registrar evento.

#### Scenario: Cambio de método
- **WHEN** el widget elige `local` en una solicitud `pending` que lo permite
- **THEN** el proveedor pasa a `local`, queda el evento `provider_selected` y el contexto lo refleja

#### Scenario: Método no permitido
- **WHEN** el widget elige un método que no está entre los disponibles
- **THEN** responde `422` con `code: provider_not_allowed` y no cambia nada

#### Scenario: Solicitud en curso o terminada
- **WHEN** la solicitud ya está `signing`, `signed` o `failed`
- **THEN** responde `409` y no cambia nada

#### Scenario: Sin token válido
- **WHEN** falta el token del widget o corresponde a otra solicitud
- **THEN** responde `401`
