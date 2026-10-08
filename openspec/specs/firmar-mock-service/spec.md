# firmar-mock-service Specification

## Purpose
TBD - created by archiving change proveedor-firmar-simulado. Update Purpose after archive.

## Requirements

### Requirement: Disponibilidad del simulado
Las rutas `/mock/firmar/**` SHALL existir únicamente con `FIRMADOC_FIRMAR_MOCK_ENABLED=true`; en otro caso SHALL responder `404`. Con el simulado habilitado, su autoridad certificante SHALL sumarse a las anclas de verificación de Firmadoc.

#### Scenario: Deshabilitado
- **WHEN** la bandera está apagada
- **THEN** todas las rutas del simulado responden `404`

### Requirement: Autenticación OAuth simulada
`POST /mock/firmar/oauth/token` SHALL aceptar `grant_type=client_credentials` con `client_id` y `client_secret` y devolver un `access_token` de tipo `Bearer` con vencimiento; con credenciales incorrectas SHALL responder `401` con `{"error": "invalid_client"}`. Las demás rutas SHALL exigir un token vigente.

#### Scenario: Credenciales válidas
- **WHEN** se piden credenciales con el cliente configurado
- **THEN** responde `200` con `access_token`, `token_type: Bearer` y `expires_in`

#### Scenario: Credenciales inválidas
- **WHEN** el secreto es incorrecto
- **THEN** responde `401`

#### Scenario: Sin token
- **WHEN** se llama a una operación sin token válido
- **THEN** responde `401`

### Requirement: Operaciones de firma simuladas
`POST /mock/firmar/v1/operations` SHALL aceptar un único documento (`document_base64`), el CUIL del firmante y la `callback_url`, y devolver `201` con `operation_id`, `status: pending` y `authorization_url`. `POST …/{id}/approve` con `otp` y `pin` correctos SHALL firmar el PDF con un certificado emitido por la AC del simulado para ese CUIL y SHALL invocar el callback con el PDF firmado y la firma HMAC; con datos incorrectos SHALL responder `403` y bloquear la operación tras 3 intentos. `POST …/{id}/reject` SHALL invocar el callback con `status: rejected`. `GET …/{id}` SHALL informar el estado.

#### Scenario: Aprobación
- **WHEN** el usuario aprueba con OTP y PIN correctos
- **THEN** el simulado llama al callback con `status: signed` y el PDF firmado

#### Scenario: OTP incorrecto
- **WHEN** el OTP o el PIN son incorrectos
- **THEN** responde `403` y no se llama al callback; al tercer intento fallido la operación queda bloqueada

#### Scenario: Más de un documento
- **WHEN** se envía más de un documento en la operación
- **THEN** responde `422` (límite del simulado, a verificar con el servicio real)
