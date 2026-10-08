## ADDED Requirements

### Requirement: Verificación del sello de tiempo
`POST /api/v1/documents/{id}/verify` SHALL informar, por cada firma, si tiene sello de tiempo, su fecha, y si el sello es íntegro, válido y de confianza (la TSA llega a un ancla configurada). Una firma con sello SHALL considerarse correcta (`ok`) solo si además su sello es íntegro, válido y de confianza. Una firma sin sello SHALL seguir siendo correcta si lo demás lo es.

#### Scenario: Firma con sello de confianza
- **WHEN** la firma tiene un sello cuya TSA llega a un ancla configurada
- **THEN** `timestamp.present` es verdadero, `timestamp.trusted` es verdadero, se informa la fecha del sello y la firma es `ok`

#### Scenario: Sello de una TSA desconocida
- **WHEN** la TSA no llega a ninguna ancla configurada
- **THEN** `timestamp.trusted` es falso y la firma no es `ok`, aunque su integridad sea correcta

#### Scenario: Firma sin sello
- **WHEN** la firma no tiene sello
- **THEN** `timestamp.present` es falso y la firma puede ser `ok`
