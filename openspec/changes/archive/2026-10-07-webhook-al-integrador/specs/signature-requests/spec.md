## MODIFIED Requirements

### Requirement: Crear solicitud de firma
`POST /api/v1/signature-requests` SHALL crear una `SignatureRequest` en estado `pending` sobre un `Document` y responder `201` con `id`, `document_id`, `status`, `signing_url` y `created_at`. La `signing_url` SHALL tener la forma `{public_base_url}/sign/{id}#t={token}`, donde el token es la credencial acotada y de corta vida del widget para esa solicitud. Si se envía `callback_url`, SHALL validarse y conservarse en la solicitud para notificar al integrador cuando termine.

#### Scenario: Documento nuevo
- **WHEN** el integrador envía `document_base64` con un PDF válido, `signer` y `provider`
- **THEN** se crea el `Document` y su `DocumentVersion` número 1 con `origin: uploaded`, y la respuesta es `201`

#### Scenario: Documento existente
- **WHEN** el integrador envía un `document_id` que le pertenece, sin `document_base64`
- **THEN** la solicitud opera sobre el mismo `Document` sin crear una versión nueva

#### Scenario: Documento de otro integrador
- **WHEN** el `document_id` pertenece a otro sistema integrador
- **THEN** la respuesta es `404`

#### Scenario: Archivo inválido
- **WHEN** `document_base64` no es base64 válido, no es un PDF o excede el tamaño máximo
- **THEN** la respuesta es `422` con el detalle del motivo

#### Scenario: Proveedor token habilitado
- **WHEN** `provider` es `token`
- **THEN** la solicitud se crea con `201` igual que con `local`

#### Scenario: Proveedor no habilitado
- **WHEN** `provider` es `firmar` y ese proveedor aún no está disponible
- **THEN** la respuesta es `422` indicando que el proveedor no está habilitado

#### Scenario: URL de firma con token
- **WHEN** se crea una solicitud
- **THEN** la `signing_url` termina en `#t=<token>`, el token solo sirve para esa solicitud y vence a la hora por defecto

#### Scenario: Callback válido
- **WHEN** se envía una `callback_url` pública `https`
- **THEN** la solicitud se crea y la URL queda guardada

#### Scenario: Callback inválido
- **WHEN** `callback_url` es insegura (esquema no permitido, credenciales en la URL, host privado o que resuelve a una dirección privada)
- **THEN** la respuesta es `422` con `code: "invalid_callback_url"` y no se crea ninguna solicitud ni documento

### Requirement: Completar la firma
`POST /api/v1/signature-requests/{id}/complete` SHALL verificar que cada firma corresponde a un desafío vigente, incrustar la firma PAdES como actualización incremental, crear la nueva `DocumentVersion` `signed`, actualizar `Document.current_version_id` y `signing_status`, registrar la notificación al integrador cuando hay `callback_url`, y responder `200` con el bloque `document`.

#### Scenario: Firma completada
- **WHEN** se completa una solicitud con un desafío vigente y una firma válida
- **THEN** la solicitud pasa a `signed`, se crea una versión con `origin: signed` y `is_active_version: true`, la versión anterior no se modifica, y la respuesta incluye `download_url` y `signed_document_base64`

#### Scenario: Desafío vencido
- **WHEN** el desafío superó su `expires_at`
- **THEN** la respuesta es `409` y no se crea ninguna versión

#### Scenario: Desafío ya usado
- **WHEN** se intenta completar con un desafío con `consumed_at` establecido
- **THEN** la respuesta es `409`

#### Scenario: Desafío de otra sesión
- **WHEN** el desafío fue preparado para otra sesión de firmante
- **THEN** la respuesta es `409`

#### Scenario: Firma que no verifica
- **WHEN** la firma enviada no verifica contra el hash preparado
- **THEN** la respuesta es `422`, la solicitud pasa a `failed` y se registra el evento `failed`

#### Scenario: Notificación al completar
- **WHEN** la solicitud tiene `callback_url` y se completa la firma
- **THEN** queda registrada una entrega `pending` del evento `signature.signed`
