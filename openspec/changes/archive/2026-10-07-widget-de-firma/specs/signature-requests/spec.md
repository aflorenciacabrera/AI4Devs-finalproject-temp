## MODIFIED Requirements

### Requirement: Crear solicitud de firma
`POST /api/v1/signature-requests` SHALL crear una `SignatureRequest` en estado `pending` sobre un `Document` y responder `201` con `id`, `document_id`, `status`, `signing_url` y `created_at`. La `signing_url` SHALL tener la forma `{public_base_url}/sign/{id}#t={token}`, donde el token es la credencial acotada y de corta vida del widget para esa solicitud.

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
