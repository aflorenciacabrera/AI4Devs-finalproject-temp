# Document Storage Specification

## Purpose

Almacenamiento inmutable de los binarios de cada versión de documento y su hash de integridad.

## Requirements

### Requirement: Almacenamiento de binarios por versión
Cada `DocumentVersion` SHALL referenciar su binario mediante `storage_ref`, y el binario SHALL ser inmutable una vez escrito.

#### Scenario: Guardar una versión
- **WHEN** se crea una versión
- **THEN** su binario queda guardado y `storage_ref` permite recuperarlo

#### Scenario: No sobrescribir
- **WHEN** se intenta guardar un binario con un `storage_ref` ya existente
- **THEN** la operación falla y el binario original permanece intacto

### Requirement: Hash de integridad
Cada `DocumentVersion` SHALL registrar el SHA-256 de su binario en `document_hash`, calculado al guardarlo.

#### Scenario: Hash coherente
- **WHEN** se lee el binario de una versión y se calcula su SHA-256
- **THEN** coincide con `document_hash`

### Requirement: Aislamiento de rutas
Las referencias de almacenamiento SHALL resolverse siempre dentro del directorio de almacenamiento configurado.

#### Scenario: Referencia maliciosa
- **WHEN** un `storage_ref` intenta salir del directorio (por ejemplo con `..`)
- **THEN** la operación se rechaza
