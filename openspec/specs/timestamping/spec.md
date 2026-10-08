# timestamping Specification

## Purpose
TBD - created by archiving change sello-de-tiempo. Update Purpose after archive.

## Requirements

### Requirement: Configuración de la TSA
Firmadoc SHALL aceptar una autoridad de sellado de tiempo RFC 3161 mediante `FIRMADOC_TSA_URL` (http o https), con tiempo límite `FIRMADOC_TSA_TIMEOUT_SECONDS` (10 por defecto) y una opción `FIRMADOC_TSA_REQUIRED` (falsa por defecto) que indica si el sello es obligatorio. Sin `FIRMADOC_TSA_URL`, las firmas SHALL completarse sin sello. Una URL con otro esquema SHALL rechazarse al cargar la configuración.

#### Scenario: Sin TSA
- **WHEN** no hay `FIRMADOC_TSA_URL`
- **THEN** no se intenta ningún sellado

#### Scenario: URL inválida
- **WHEN** `FIRMADOC_TSA_URL` no empieza con `http://` ni `https://`
- **THEN** la configuración se rechaza

### Requirement: Sello de tiempo de la firma
Con una TSA configurada, `complete` SHALL pedir a la TSA el sello de la firma (la firma, no el documento) e incrustarlo como atributo no firmado de la firma CMS (PAdES B-T), y la `DocumentVersion` resultante SHALL registrar `signature_level` `B-T`. Sin sello, el nivel SHALL ser `B-B`.

#### Scenario: Firma con sello
- **WHEN** la TSA devuelve un sello válido
- **THEN** el PDF contiene la firma con su sello y una herramienta independiente verifica ambos

#### Scenario: Sello atado a la firma
- **WHEN** se altera la firma dentro del PDF
- **THEN** la verificación de la firma y la del sello fallan

### Requirement: Disponibilidad de la TSA
Si la TSA no responde, devuelve un error o un sello inválido, `complete` SHALL conservar el desafío sin consumir hasta decidir según `FIRMADOC_TSA_REQUIRED`: con sello obligatorio SHALL responder `503` con `code: timestamp_unavailable` sin cambiar el estado de la solicitud ni consumir el desafío (se puede reintentar `complete` sin volver a firmar); sin sello obligatorio SHALL completar la firma en nivel `B-B` y SHALL registrar el evento de auditoría `timestamp_unavailable` con el motivo.

#### Scenario: TSA caída, sello obligatorio
- **WHEN** la TSA no responde y el sello es obligatorio
- **THEN** responde `503`, la solicitud sigue en `signing` y reintentar `complete` cuando la TSA vuelve produce la firma con sello

#### Scenario: TSA caída, sello opcional
- **WHEN** la TSA no responde y el sello no es obligatorio
- **THEN** la firma se completa en `B-B` y queda el evento `timestamp_unavailable`

#### Scenario: Tiempo agotado
- **WHEN** la TSA tarda más que `FIRMADOC_TSA_TIMEOUT_SECONDS`
- **THEN** se trata como no disponible
