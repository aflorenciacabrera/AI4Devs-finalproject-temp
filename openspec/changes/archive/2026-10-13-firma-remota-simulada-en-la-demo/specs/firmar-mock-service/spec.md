## ADDED Requirements

### Requirement: Página de autorización del usuario
El simulado SHALL servir en la `authorization_url` que devuelve (`GET /mock/firmar/authorize/{operation_id}`) una página HTML con un formulario de OTP y PIN y una opción para rechazar, sin exigir el token OAuth (es la pantalla de la persona firmante, no una ruta de la API). `POST` a la misma ruta con el formulario SHALL comportarse como las rutas `approve` y `reject`: con OTP `123456` y PIN `1234` firma el PDF, invoca el callback y muestra que la firma se completó y que hay que volver a Firmadoc; con datos incorrectos muestra el error y, al tercer intento fallido, bloquea la operación; con «Rechazar» invoca el callback con `status: rejected`. Una operación que ya no está pendiente SHALL mostrar su estado sin ofrecer el formulario. Una operación inexistente SHALL responder `404`. La página SHALL indicar que es un servicio simulado y los códigos válidos.

#### Scenario: Formulario
- **WHEN** se abre la `authorization_url` de una operación pendiente
- **THEN** responde `200` con un formulario de OTP y PIN y un botón para rechazar

#### Scenario: Aprobación desde la página
- **WHEN** se envía el formulario con OTP `123456` y PIN `1234`
- **THEN** el simulado llama al callback con `status: signed` y la página informa que la firma se completó

#### Scenario: Datos incorrectos y bloqueo
- **WHEN** se envía el formulario con un OTP o PIN incorrecto tres veces
- **THEN** las dos primeras muestran el error y la tercera informa que la operación quedó bloqueada; el callback no se llama

#### Scenario: Rechazo desde la página
- **WHEN** se elige «Rechazar»
- **THEN** el simulado llama al callback con `status: rejected` y la página lo informa

#### Scenario: Operación inexistente o simulado apagado
- **WHEN** el identificador no existe, o `FIRMADOC_FIRMAR_MOCK_ENABLED` está apagado
- **THEN** responde `404`

## MODIFIED Requirements

### Requirement: Autenticación OAuth simulada
`POST /mock/firmar/oauth/token` SHALL aceptar `grant_type=client_credentials` con `client_id` y `client_secret` y devolver un `access_token` de tipo `Bearer` con vencimiento; con credenciales incorrectas SHALL responder `401` con `{"error": "invalid_client"}`. Las demás rutas de la API (`/v1/**`) SHALL exigir un token vigente; la página de autorización del usuario (`/authorize/**`) no lo exige.

#### Scenario: Credenciales válidas
- **WHEN** se piden credenciales con el cliente configurado
- **THEN** responde `200` con `access_token`, `token_type: Bearer` y `expires_in`

#### Scenario: Credenciales inválidas
- **WHEN** el secreto es incorrecto
- **THEN** responde `401`

#### Scenario: Sin token
- **WHEN** se llama a una ruta de la API sin token válido
- **THEN** responde `401`
