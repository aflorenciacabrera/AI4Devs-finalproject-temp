## MODIFIED Requirements

### Requirement: Vinculación de identidad por CUIL
El CUIL del certificado SHALL extraerse del atributo `serialNumber` del sujeto con formato `CUIL <11 dígitos>` y registrarse junto con la firma (vacío si el certificado no lo trae). La comparación con el `identifier` del firmante SHALL hacerse **solo** cuando la configuración lo exige (`FIRMADOC_REQUIRE_CUIL_MATCH=true`, por defecto `false`): en ese caso, ignorando guiones y espacios, si no coincide o el certificado no contiene CUIL, SHALL rechazarse como error de identidad (`403`, código `cuil_mismatch`). Sin esa configuración, un certificado válido SHALL aceptarse cualquiera sea su CUIL, y el único factor que se exige al firmante es el PIN de su token, que se ingresa en el agente.

#### Scenario: Cotejo desactivado (por defecto)
- **WHEN** el certificado es válido y su CUIL difiere del `identifier` del firmante, o no tiene CUIL
- **THEN** la validación es correcta y el CUIL registrado es el del certificado (o ninguno)

#### Scenario: CUIL coincide
- **WHEN** `FIRMADOC_REQUIRE_CUIL_MATCH=true` (cotejo activado), el certificado trae `serialNumber=CUIL 20123456789` y el firmante tiene identifier `20-12345678-9`
- **THEN** la vinculación es válida

#### Scenario: CUIL distinto
- **WHEN** `FIRMADOC_REQUIRE_CUIL_MATCH=true` (cotejo activado) y el CUIL del certificado difiere del del firmante
- **THEN** se rechaza con `403` y código `cuil_mismatch`

#### Scenario: Certificado sin CUIL
- **WHEN** `FIRMADOC_REQUIRE_CUIL_MATCH=true` (cotejo activado) y el sujeto no tiene `serialNumber` con formato de CUIL
- **THEN** se rechaza con `403` y código `cuil_mismatch`
