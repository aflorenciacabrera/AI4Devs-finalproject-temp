## MODIFIED Requirements

### Requirement: Preparar un lote
`POST /api/v1/signature-batches/{id}/prepare` SHALL preparar cada solicitud del lote con el mismo certificado y SHALL devolver un desafío por documento, cada uno de un solo uso y atado a la misma sesión.

#### Scenario: Preparación
- **WHEN** se prepara un lote de tres documentos con un certificado válido
- **THEN** responde `200` con tres desafíos, uno por solicitud, y las solicitudes pasan a `signing`

#### Scenario: Certificado rechazado
- **WHEN** el certificado no es de confianza, está vencido o revocado, o (solo con `FIRMADOC_REQUIRE_CUIL_MATCH=true`) su CUIL no coincide con el del firmante
- **THEN** responde con el mismo error que `prepare` de una solicitud y ninguna solicitud cambia de estado
