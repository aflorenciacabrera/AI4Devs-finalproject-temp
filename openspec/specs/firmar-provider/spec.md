# firmar-provider Specification

## Purpose
TBD - created by archiving change proveedor-firmar-simulado. Update Purpose after archive.

## Requirements

### Requirement: Habilitación del proveedor
El proveedor `firmar` SHALL estar habilitado únicamente cuando `FIRMADOC_FIRMAR_BASE_URL` está configurada; en otro caso crear una solicitud con `provider: firmar` SHALL responder `422` indicando que no está habilitado. El secreto del callback SHALL tener al menos 32 caracteres y se SHALL validar al cargar la configuración.

#### Scenario: Sin configurar
- **WHEN** no hay `FIRMADOC_FIRMAR_BASE_URL`
- **THEN** crear una solicitud `firmar` responde `422`

#### Scenario: Configurado
- **WHEN** la URL base está configurada
- **THEN** la solicitud `firmar` se crea con `201` como las demás

#### Scenario: Secreto de callback corto
- **WHEN** `FIRMADOC_FIRMAR_CALLBACK_SECRET` tiene menos de 32 caracteres
- **THEN** la configuración se rechaza

### Requirement: Preparar una firma remota
`prepare` de una solicitud `firmar` SHALL autenticarse contra el servicio con OAuth2 *client credentials*, enviarle el PDF de la versión vigente con el CUIL del firmante y la URL del callback, guardar el `operation_id` recibido, pasar la solicitud a `signing`, registrar el evento `prepared` y responder `200` con `challenges: []` y un bloque `remote` con `operation_id` y `authorization_url`. SHALL NOT crear ningún `SigningChallenge`.

#### Scenario: Preparación exitosa
- **WHEN** se prepara una solicitud `firmar` y el servicio responde
- **THEN** la solicitud queda en `signing` con su `remote_operation_id` y la respuesta trae `remote.authorization_url`

#### Scenario: Servicio no disponible
- **WHEN** el servicio no responde, devuelve un error o rechaza las credenciales
- **THEN** responde `503` con `code: remote_unavailable`, sin reproducir el cuerpo del servicio, y la solicitud conserva su estado

#### Scenario: Completar no aplica
- **WHEN** se llama a `complete` sobre una solicitud `firmar`
- **THEN** responde `409` con `code: remote_signature_pending` y no cambia nada

### Requirement: Callback de resultado
`POST /api/v1/providers/firmar/callback` SHALL exigir la cabecera `X-Firmar-Signature: sha256=<HMAC-SHA256 del cuerpo crudo con FIRMADOC_FIRMAR_CALLBACK_SECRET>` comparada en tiempo constante, SHALL ubicar la solicitud por `remote_operation_id` y SHALL ser idempotente: si la solicitud ya está `signed` o `failed`, SHALL responder `200` con `status: already_processed` sin modificar nada. Sin proveedor configurado SHALL responder `404`.

#### Scenario: Firma inválida
- **WHEN** la cabecera falta o no corresponde al cuerpo
- **THEN** responde `401` y no cambia nada

#### Scenario: Operación desconocida
- **WHEN** el `operation_id` no corresponde a ninguna solicitud
- **THEN** responde `404`

#### Scenario: Repetición
- **WHEN** el servicio reenvía un callback ya procesado
- **THEN** responde `200` con `already_processed` y no crea otra versión

#### Scenario: Rechazo o vencimiento
- **WHEN** el estado informado es `rejected` o `expired`
- **THEN** la solicitud pasa a `failed`, se registra el evento `failed` y se notifica al integrador si hay `callback_url`

### Requirement: Validación del PDF devuelto
Ante un callback `signed`, antes de crear la versión Firmadoc SHALL comprobar que el PDF devuelto comienza con los mismos bytes de la versión vigente (solo se agregó una actualización incremental), que contiene exactamente una firma más, que esa firma es íntegra y su cadena llega a las anclas de confianza, y que el CUIL de su certificado coincide con el del firmante de la solicitud. Si todo es correcto SHALL registrar el certificado, crear la `DocumentVersion` `signed` vigente sin modificar la anterior, pasar la solicitud a `signed` y registrar la auditoría y el webhook como cualquier otra firma. Si algo falla SHALL pasar la solicitud a `failed` con el motivo y responder `422`.

#### Scenario: Firma remota válida
- **WHEN** llega un PDF que extiende al enviado con una firma de confianza del CUIL esperado
- **THEN** la solicitud queda `signed`, hay una versión nueva vigente con la anterior intacta y el certificado figura con proveedor `firmar`

#### Scenario: Contenido alterado
- **WHEN** el PDF devuelto no conserva byte a byte el contenido enviado
- **THEN** responde `422`, la solicitud pasa a `failed` y no se crea versión

#### Scenario: Sin firma nueva
- **WHEN** el PDF devuelto no agrega ninguna firma, o agrega más de una
- **THEN** responde `422` y la solicitud pasa a `failed`

#### Scenario: Cadena desconocida
- **WHEN** la firma no llega a ninguna ancla de confianza
- **THEN** responde `422` y la solicitud pasa a `failed`

#### Scenario: CUIL distinto
- **WHEN** el CUIL del certificado no es el del firmante
- **THEN** responde `422` con `code: cuil_mismatch` y la solicitud pasa a `failed`

#### Scenario: Cuerpo inválido
- **WHEN** el cuerpo no es JSON válido, falta `signed_document_base64` en un resultado `signed`, o supera el tamaño máximo
- **THEN** responde `422`
