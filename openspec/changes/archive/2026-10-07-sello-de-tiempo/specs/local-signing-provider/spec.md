## MODIFIED Requirements

### Requirement: Firma electrónica con certificado propio
El proveedor `local` SHALL firmar con un certificado autofirmado de demostración propio de Firmadoc, y las firmas resultantes SHALL ser PAdES de nivel B-B (o B-T cuando hay una TSA configurada) verificables por una herramienta independiente.

#### Scenario: Firma verificable
- **WHEN** se completa una solicitud `local`
- **THEN** el PDF resultante contiene una firma PAdES cuya integridad verifica con una herramienta independiente de la que la produjo

#### Scenario: Sin servicios externos
- **WHEN** no hay conectividad de red y no hay TSA configurada
- **THEN** el flujo `local` se completa de punta a punta
