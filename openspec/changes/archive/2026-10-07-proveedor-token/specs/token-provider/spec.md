## ADDED Requirements

### Requirement: Preparar con el certificado del token
Para `provider: token`, `prepare` SHALL exigir `certificate_pem`, validarlo y vincular su CUIL con el firmante **antes** de generar el desafío, de modo que un certificado inválido se informe antes de que el usuario ingrese el PIN.

#### Scenario: Certificado válido
- **WHEN** se prepara una solicitud `token` con un certificado válido cuyo CUIL coincide con el firmante
- **THEN** la respuesta contiene el desafío con el hash a firmar y el certificado queda registrado con sus datos públicos y su estado de revocación

#### Scenario: Falta el certificado
- **WHEN** se prepara una solicitud `token` sin `certificate_pem`
- **THEN** la respuesta es `422` con código `certificate_invalid`

#### Scenario: Certificado rechazado
- **WHEN** el certificado está vencido, revocado o es de una cadena no confiable
- **THEN** no se crea ningún desafío, la solicitud sigue en `pending` y la respuesta es `422` con el código correspondiente

#### Scenario: CUIL de otra persona
- **WHEN** el CUIL del certificado no es el del firmante
- **THEN** la respuesta es `403` con código `cuil_mismatch` y no se crea ningún desafío

### Requirement: Clave privada solo en el token
El flujo `token` SHALL funcionar sin que el servidor conozca la clave privada ni reciba el PIN: el servidor SHALL recibir únicamente el certificado público y las firmas del hash.

#### Scenario: Complete sin firma
- **WHEN** se invoca `complete` en una solicitud `token` con `signatures: []`
- **THEN** la respuesta es `422` indicando que la firma es obligatoria y el desafío permanece sin consumir

### Requirement: Formato de la firma del token
La firma enviada en `signature_base64` SHALL ser RSA PKCS#1 v1.5 sobre la estructura `DigestInfo` de SHA-256 del `hash_to_sign` decodificado, codificada en base64; el servidor SHALL verificarla con la clave pública del certificado antes de incrustarla.

#### Scenario: Firma correcta
- **WHEN** el agente firma el `DigestInfo` del hash con la clave del certificado preparado
- **THEN** `complete` incrusta la firma y crea la nueva versión vigente

#### Scenario: Firma hecha con otra clave
- **WHEN** la firma fue producida con una clave distinta de la del certificado
- **THEN** la respuesta es `422`, la solicitud pasa a `failed` y el desafío no se consume

#### Scenario: Firma de otro hash
- **WHEN** la firma corresponde a un hash distinto del preparado
- **THEN** la respuesta es `422` y la solicitud pasa a `failed`

### Requirement: Revalidación al completar
`complete` SHALL revalidar el certificado del desafío (vigencia y revocación) antes de incrustar la firma, y SHALL verificar el PDF resultante contra las anclas de confianza; si algo falla no se crea ninguna versión.

#### Scenario: Revocado entre prepare y complete
- **WHEN** el certificado se revoca después de `prepare`
- **THEN** `complete` responde `422` con `certificate_revoked`, la solicitud pasa a `failed` y no se crea ninguna versión

#### Scenario: PDF resultante verificado
- **WHEN** se completa una firma `token` válida
- **THEN** el PDF de la nueva versión valida con una herramienta independiente y la cadena del firmante llega a un ancla de confianza

### Requirement: Varias firmas sobre un documento
Un documento ya firmado SHALL poder firmarse con `token` por otro funcionario, agregando la firma como actualización incremental sin invalidar las anteriores, incluso si fue firmado con un proveedor distinto.

#### Scenario: Firma local seguida de firma con token
- **WHEN** un documento firmado con `local` se firma luego con `token`
- **THEN** la versión resultante contiene ambas firmas y la primera sigue siendo íntegra

### Requirement: Contrato documentado con el agente
El contrato entre Firmadoc y el agente local (hash, algoritmo, codificación y errores) SHALL estar documentado en `docs/agent-contract.md` y SHALL ser el que implementa el simulador de agente usado en los tests.

#### Scenario: Simulador conforme
- **WHEN** el simulador de agente firma un desafío siguiendo el documento
- **THEN** el flujo `token` se completa de punta a punta
