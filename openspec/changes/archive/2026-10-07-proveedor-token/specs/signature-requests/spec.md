## MODIFIED Requirements

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

#### Scenario: Proveedor token habilitado
- **WHEN** `provider` es `token`
- **THEN** la solicitud se crea con `201` igual que con `local`

#### Scenario: Proveedor no habilitado
- **WHEN** `provider` es `firmar` y ese proveedor aún no está disponible
- **THEN** la respuesta es `422` indicando que el proveedor no está habilitado

### Requirement: Preparar la firma
`POST /api/v1/signature-requests/{id}/prepare` SHALL calcular el hash a firmar, crear un `SigningChallenge` de un solo uso con vencimiento y atado a la sesión, pasar la solicitud a `signing` y responder `200` con `challenges` y `expires_at`. Cuando el proveedor valida un certificado, los rechazos SHALL responder con un cuerpo `{detail, code}` y no SHALL crear ningún desafío.

#### Scenario: Preparación exitosa
- **WHEN** se prepara una solicitud en estado `pending`
- **THEN** la respuesta contiene un desafío con `challenge_id`, `document_name`, `hash_algorithm: SHA-256` y `hash_to_sign`, y se registra el evento de auditoría `prepared`

#### Scenario: Solicitud ajena o inexistente
- **WHEN** la solicitud no existe o pertenece a otro sistema integrador
- **THEN** la respuesta es `404`

#### Scenario: Estado inválido
- **WHEN** la solicitud ya está `signed` o `failed`
- **THEN** la respuesta es `409`

#### Scenario: Certificado rechazado
- **WHEN** el proveedor rechaza el certificado enviado
- **THEN** la respuesta es `403` (identidad) o `422` (certificado) con `code`, la solicitud permanece en su estado y se registra el evento de auditoría `rejected` con el motivo
