## MODIFIED Requirements

### Requirement: Preparar con el certificado del token
Para `provider: token`, `prepare` SHALL exigir `certificate_pem` y validarlo (cadena de confianza, vigencia, uso de clave, revocación y algoritmo) **antes** de generar el desafío, de modo que un certificado inválido se informe antes de que el usuario ingrese el PIN. SHALL vincular el CUIL del certificado con el firmante solo si `FIRMADOC_REQUIRE_CUIL_MATCH=true`; por defecto, cualquier certificado válido firma y la solicitud registra el sujeto y el CUIL del certificado usado.

#### Scenario: Certificado válido
- **WHEN** se prepara una solicitud `token` con un certificado válido
- **THEN** la respuesta contiene el desafío con el hash a firmar y el certificado queda registrado con sus datos públicos, su CUIL (si lo tiene) y su estado de revocación

#### Scenario: Certificado de otra persona sin cotejo
- **WHEN** el cotejo de CUIL está desactivado (por defecto) y el CUIL del certificado no es el del firmante de la solicitud, o el certificado no tiene CUIL
- **THEN** la respuesta es `200` con el desafío, y la firma completada queda asociada al sujeto y CUIL de ese certificado

#### Scenario: Falta el certificado
- **WHEN** se prepara una solicitud `token` sin `certificate_pem`
- **THEN** la respuesta es `422` con código `certificate_invalid`

#### Scenario: Certificado rechazado
- **WHEN** el certificado está vencido, revocado o es de una cadena no confiable
- **THEN** no se crea ningún desafío, la solicitud sigue en `pending` y la respuesta es `422` con el código correspondiente

#### Scenario: CUIL de otra persona
- **WHEN** `FIRMADOC_REQUIRE_CUIL_MATCH=true` (cotejo activado) y el CUIL del certificado no es el del firmante
- **THEN** la respuesta es `403` con código `cuil_mismatch` y no se crea ningún desafío
