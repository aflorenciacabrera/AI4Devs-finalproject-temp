# document-status Specification

## Purpose
TBD - created by archiving change estado-y-verificacion-de-documentos. Update Purpose after archive.

## Requirements

### Requirement: Consultar un documento
`GET /api/v1/documents/{id}` SHALL devolver `signing_status`, `signature_deadline`, `deadline_passed`, el `external_document_id` y la versión vigente (número y URL de descarga), solo para el integrador dueño, y SHALL rechazar con `401` una API key inválida.

#### Scenario: Documento propio
- **WHEN** el integrador consulta un documento suyo
- **THEN** recibe su estado, plazo y versión vigente

#### Scenario: Documento ajeno
- **WHEN** otro integrador lo consulta
- **THEN** responde `404`

#### Scenario: Plazo vencido
- **WHEN** `signature_deadline` es anterior al momento de la consulta
- **THEN** `deadline_passed` es verdadero y el documento sigue pudiendo firmarse

### Requirement: Cambiar el estado de firma
`PATCH /api/v1/documents/{id}` SHALL permitir fijar `signing_status` en `draft` o `pending_signature`, y SHALL rechazar con `422` el valor `signed` o cualquier otro. Un documento `signed` SHALL poder pasar a `pending_signature` pero no a `draft`.

#### Scenario: Marcar pendiente
- **WHEN** un documento en `draft` se marca `pending_signature`
- **THEN** responde `200` con el nuevo estado

#### Scenario: Volver a borrador
- **WHEN** un documento en `pending_signature` se marca `draft`
- **THEN** responde `200`

#### Scenario: Firmado no vuelve a borrador
- **WHEN** un documento `signed` se marca `draft`
- **THEN** responde `409` y no cambia

#### Scenario: Nueva ronda de firmas
- **WHEN** un documento `signed` se marca `pending_signature`
- **THEN** responde `200`; al completarse otra firma vuelve a `signed`

#### Scenario: Estado no permitido
- **WHEN** se intenta fijar `signed`
- **THEN** responde `422`

### Requirement: Fecha límite de firma
`PATCH` SHALL permitir fijar `signature_deadline` con zona horaria y en el futuro, o borrarla con `null`, y SHALL rechazar con `422` una fecha sin zona o pasada. Firmadoc SHALL tratar el plazo como informativo y no bloquear firmas por plazo vencido.

#### Scenario: Fijar y borrar
- **WHEN** se envía una fecha futura con zona y luego `null`
- **THEN** el plazo queda fijado y después vacío

#### Scenario: Fecha inválida
- **WHEN** la fecha no tiene zona horaria o ya pasó
- **THEN** responde `422` y no cambia nada

#### Scenario: Cuerpo vacío
- **WHEN** el cuerpo no trae ningún campo
- **THEN** responde `422`
