## ADDED Requirements

### Requirement: Autenticación del sistema integrador
Todos los endpoints de `/api/v1` del flujo de firma SHALL exigir la cabecera `X-API-Key` y SHALL compararla contra `IntegratingSystem.api_key_hash`; una clave ausente o inválida SHALL responder `401`.

#### Scenario: Clave ausente
- **WHEN** se invoca cualquier endpoint del flujo sin `X-API-Key`
- **THEN** la respuesta es `401`

#### Scenario: Clave inválida
- **WHEN** se invoca con una `X-API-Key` que no corresponde a ningún sistema integrador
- **THEN** la respuesta es `401`

### Requirement: Crear solicitud de firma
`POST /api/v1/signature-requests` SHALL crear una `SignatureRequest` en estado `pending` sobre un `Document` y responder `201` con `id`, `document_id`, `status`, `signing_url` y `created_at`.

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

#### Scenario: Proveedor no habilitado
- **WHEN** `provider` es `token` o `firmar` y ese proveedor aún no está disponible
- **THEN** la respuesta es `422` indicando que el proveedor no está habilitado

### Requirement: Preparar la firma
`POST /api/v1/signature-requests/{id}/prepare` SHALL calcular el hash a firmar, crear un `SigningChallenge` de un solo uso con vencimiento y atado a la sesión, pasar la solicitud a `signing` y responder `200` con `challenges` y `expires_at`.

#### Scenario: Preparación exitosa
- **WHEN** se prepara una solicitud en estado `pending`
- **THEN** la respuesta contiene un desafío con `challenge_id`, `document_name`, `hash_algorithm: SHA-256` y `hash_to_sign`, y se registra el evento de auditoría `prepared`

#### Scenario: Solicitud ajena o inexistente
- **WHEN** la solicitud no existe o pertenece a otro sistema integrador
- **THEN** la respuesta es `404`

#### Scenario: Estado inválido
- **WHEN** la solicitud ya está `signed` o `failed`
- **THEN** la respuesta es `409`

### Requirement: Completar la firma
`POST /api/v1/signature-requests/{id}/complete` SHALL verificar que cada firma corresponde a un desafío vigente, incrustar la firma PAdES como actualización incremental, crear la nueva `DocumentVersion` `signed`, actualizar `Document.current_version_id` y `signing_status`, y responder `200` con el bloque `document`.

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

### Requirement: Descarga y versionado simultáneos
Toda firma completada SHALL dejar el documento descargable y versionado a la vez, sin modificar ni eliminar versiones anteriores.

#### Scenario: Descarga de una versión
- **WHEN** se invoca `GET /api/v1/documents/{document_id}/versions/{n}/download` de un documento propio
- **THEN** la respuesta es `200` con el PDF de esa versión (`application/pdf`)

#### Scenario: Segunda firma sobre el mismo documento
- **WHEN** se firma por segunda vez un documento ya firmado
- **THEN** se crea la versión 3 sobre la versión 2, ambas versiones anteriores permanecen intactas y la 3 es la vigente

### Requirement: Consulta de la solicitud
`GET /api/v1/signature-requests/{id}` SHALL devolver el estado de la solicitud, el bloque `document` cuando está firmada y el historial de eventos de auditoría.

#### Scenario: Solicitud firmada
- **WHEN** se consulta una solicitud en estado `signed`
- **THEN** la respuesta incluye el bloque `document` y los eventos `created`, `prepared` y `signed` en orden

### Requirement: Auditoría del flujo
Cada transición del flujo SHALL registrar un `AuditEvent` (`created`, `prepared`, `signed`, `failed`) asociado a la solicitud.

#### Scenario: Evento al crear
- **WHEN** se crea una solicitud
- **THEN** existe un evento `created` asociado a esa solicitud
