# Certificate Validation Specification

## Purpose

Validación de certificados X.509 de firmantes contra anclas de confianza (cadena, vigencia, uso de clave, revocación, algoritmo y vínculo de identidad por CUIL) con motivos de rechazo estables.

## Requirements

### Requirement: Anclas de confianza desde disco
Firmadoc SHALL cargar como anclas de confianza los certificados `.crt`/`.pem` del directorio configurado en `FIRMADOC_TRUST_DIR`, tratando los autofirmados como raíces y el resto como intermedios, y SHALL ofrecer un comando que liste la huella SHA-256 de cada uno.

#### Scenario: Carga de anclas
- **WHEN** el directorio de confianza contiene una raíz y una AC intermedia
- **THEN** ambas quedan disponibles para validar cadenas

#### Scenario: Huellas
- **WHEN** se ejecuta `python -m firmadoc.trust list`
- **THEN** se muestra el sujeto y la huella SHA-256 de cada certificado cargado

#### Scenario: Directorio vacío
- **WHEN** no hay ningún ancla cargada
- **THEN** todo certificado de tercero se rechaza como no confiable

### Requirement: Validación de la cadena de confianza
Un certificado de firmante SHALL aceptarse solo si su cadena llega a un ancla de confianza cargada; en caso contrario SHALL rechazarse con el código `certificate_untrusted`.

#### Scenario: Cadena válida
- **WHEN** el certificado fue emitido por una AC intermedia cuya raíz está cargada
- **THEN** la validación de la cadena tiene éxito

#### Scenario: Otra AC
- **WHEN** el certificado fue emitido por una AC que no está bajo ninguna ancla cargada
- **THEN** se rechaza con `certificate_untrusted`

### Requirement: Vigencia y uso de clave
El certificado SHALL estar dentro de su período de validez y su uso de clave, si está presente, SHALL permitir firma digital o no repudio; de lo contrario SHALL rechazarse con `certificate_expired` o `certificate_invalid` respectivamente.

#### Scenario: Certificado vencido
- **WHEN** la fecha actual es posterior a `notAfter`
- **THEN** se rechaza con `certificate_expired`

#### Scenario: Certificado aún no vigente
- **WHEN** la fecha actual es anterior a `notBefore`
- **THEN** se rechaza con `certificate_invalid`

#### Scenario: Uso de clave inadecuado
- **WHEN** el uso de clave no incluye firma digital ni no repudio
- **THEN** se rechaza con `certificate_invalid`

### Requirement: Revocación
La validación SHALL consultar la revocación (CRL u OCSP) según `FIRMADOC_REVOCATION_MODE`: en `hard-fail` un estado que no pueda determinarse SHALL rechazar el certificado; en `soft-fail` SHALL aceptarlo registrando `revocation_status: unknown`; en `off` no se consulta. Un certificado revocado SHALL rechazarse siempre con `certificate_revoked` salvo en modo `off`.

#### Scenario: Certificado revocado
- **WHEN** la CRL de la AC lista el número de serie del certificado
- **THEN** se rechaza con `certificate_revoked`

#### Scenario: Estado no determinable en soft-fail
- **WHEN** no se puede obtener la CRL ni la respuesta OCSP y el modo es `soft-fail`
- **THEN** el certificado se acepta y su `revocation_status` queda `unknown`

#### Scenario: Estado no determinable en hard-fail
- **WHEN** no se puede obtener la CRL ni la respuesta OCSP y el modo es `hard-fail`
- **THEN** se rechaza con `certificate_invalid` indicando que no se pudo verificar la revocación

### Requirement: Vinculación de identidad por CUIL
El CUIL del certificado SHALL extraerse del atributo `serialNumber` del sujeto con formato `CUIL <11 dígitos>` y compararse, ignorando guiones y espacios, con el `identifier` del firmante; si no coincide, o el certificado no contiene CUIL, SHALL rechazarse como error de identidad (`403`, código `cuil_mismatch`).

#### Scenario: CUIL coincide
- **WHEN** el certificado trae `serialNumber=CUIL 20123456789` y el firmante tiene identifier `20-12345678-9`
- **THEN** la vinculación es válida

#### Scenario: CUIL distinto
- **WHEN** el CUIL del certificado difiere del del firmante
- **THEN** se rechaza con `403` y código `cuil_mismatch`

#### Scenario: Certificado sin CUIL
- **WHEN** el sujeto no tiene `serialNumber` con formato de CUIL
- **THEN** se rechaza con `403` y código `cuil_mismatch`

### Requirement: Algoritmo de clave soportado
Solo SHALL aceptarse certificados con clave pública RSA de al menos 2048 bits; otros tipos o tamaños SHALL rechazarse con `certificate_invalid`.

#### Scenario: Clave RSA débil
- **WHEN** el certificado tiene una clave RSA de 1024 bits
- **THEN** se rechaza con `certificate_invalid`

### Requirement: Códigos de error estables
Cada rechazo SHALL devolver un cuerpo con `detail` legible y `code` estable (`certificate_untrusted`, `certificate_expired`, `certificate_revoked`, `certificate_invalid`, `cuil_mismatch`).

#### Scenario: Cuerpo del error
- **WHEN** se rechaza un certificado revocado
- **THEN** la respuesta incluye `code: "certificate_revoked"` y un `detail` con el motivo
