# document-verification Specification

## Purpose
TBD - created by archiving change estado-y-verificacion-de-documentos. Update Purpose after archive.

## Requirements

### Requirement: Listar los firmantes de un documento
`GET /api/v1/documents/{id}/signatures` SHALL devolver, en orden de versión, una entrada por firma registrada con el nombre del firmante, la fecha de firma, el certificado (sujeto, emisor, número de serie), el proveedor y el número de versión resultante, solo para el integrador dueño.

#### Scenario: Dos firmantes
- **WHEN** un documento fue firmado por dos solicitudes sucesivas
- **THEN** la lista tiene dos entradas, la primera con la versión 2 y la segunda con la versión 3

#### Scenario: Sin firmas
- **WHEN** el documento no tiene versiones firmadas
- **THEN** la lista está vacía

#### Scenario: Documento ajeno
- **WHEN** otro integrador consulta la lista
- **THEN** responde `404`

### Requirement: Verificar un documento
`POST /api/v1/documents/{id}/verify` SHALL releer el PDF de la versión vigente, comparar su SHA-256 con el registrado y validar cada firma incrustada contra las anclas de confianza, y SHALL informar el resultado por firma (integridad, validez, confianza, modificaciones posteriores) y un resultado global `valid`.

#### Scenario: Documento firmado íntegro
- **WHEN** se verifica un documento firmado con el proveedor `local` o `token`
- **THEN** `hash_matches` es verdadero, cada firma es íntegra, válida y de confianza, y `valid` es verdadero

#### Scenario: Varias firmas
- **WHEN** el documento tiene dos firmas sucesivas
- **THEN** ambas se informan y la primera sigue válida

#### Scenario: Binario alterado
- **WHEN** el binario guardado fue modificado después de firmar
- **THEN** `hash_matches` es falso y `valid` es falso

#### Scenario: Ancla desconocida
- **WHEN** la cadena del firmante no llega a ninguna ancla configurada
- **THEN** esa firma figura como no confiable y `valid` es falso, sin que se pierda la información de integridad

#### Scenario: Sin firmas
- **WHEN** la versión vigente no tiene firmas
- **THEN** `valid` es falso, la lista de firmas está vacía y `hash_matches` se informa igual

#### Scenario: Binario ausente
- **WHEN** el almacenamiento no tiene el binario de la versión vigente
- **THEN** responde `409` indicando que no está disponible

#### Scenario: Documento ajeno o inexistente
- **WHEN** otro integrador verifica el documento, o el id no existe
- **THEN** responde `404`
