## ADDED Requirements

### Requirement: Verificación con certificados propios archivados
La verificación de documentos SHALL usar como anclas del proveedor `local` el certificado vigente y todos los certificados propios archivados por rotaciones anteriores, de modo que las firmas emitidas antes de una rotación sigan verificándose.

#### Scenario: Firma anterior a la rotación
- **WHEN** se verifica un documento firmado con un certificado propio ya archivado
- **THEN** su firma es válida y de confianza
