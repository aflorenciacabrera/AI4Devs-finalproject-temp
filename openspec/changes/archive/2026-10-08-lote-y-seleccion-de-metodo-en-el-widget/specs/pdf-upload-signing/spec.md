## ADDED Requirements

### Requirement: Carga de varios PDF desde el panel
`POST /api/v1/admin/signing-batch-uploads` SHALL aceptar, con el token de administración, `documents` (de 2 a `max_batch_size`, cada uno con `filename` y `document_base64`) y `signer` opcional, validar todos los PDF con las mismas reglas que la carga individual, guardarlos como versión original v1 y crear **un lote** en el sistema integrador interno del panel con los métodos `token` y `local` según estén habilitados. SHALL responder `201` con `batch_id`, `signing_url` de lote y, por documento, `document_id`, `filename`, `page_count`, `size_bytes` y `document_hash`. Es atómico: si uno es inválido no se crea nada (`422`).

#### Scenario: Lote válido
- **WHEN** se envían 3 PDF válidos con el token de administración
- **THEN** se crean 3 documentos con versión v1 y un lote con 3 solicitudes pendientes, y se devuelve la `signing_url` de lote

#### Scenario: Un archivo inválido
- **WHEN** uno de los archivos no es un PDF legible
- **THEN** responde `422` y no se crea ningún documento, versión, solicitud ni lote

#### Scenario: Cantidad fuera de rango
- **WHEN** se envían menos de 2 o más de `max_batch_size` documentos
- **THEN** responde `422`

#### Scenario: Auditoría
- **WHEN** se crea el lote
- **THEN** queda un evento de administración `panel_batch_upload` con los documentos y hashes, sin contenido
