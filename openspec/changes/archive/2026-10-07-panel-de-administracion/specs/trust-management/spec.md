## ADDED Requirements

### Requirement: Listar las anclas de confianza
`GET /api/v1/admin/trust-anchors` SHALL listar los certificados de `FIRMADOC_TRUST_DIR` con huella SHA-256, sujeto, emisor, vigencia, si es raíz y el archivo del que provienen.

#### Scenario: Listado
- **WHEN** el directorio tiene una raíz y una intermedia
- **THEN** se listan ambas con su huella y tipo

### Requirement: Agregar un ancla de confianza
`POST /api/v1/admin/trust-anchors` con `certificate_pem` SHALL validar que sea un único certificado X.509, que no esté vencido y que sea una autoridad (`basicConstraints` CA) o autofirmado, SHALL guardarlo en el directorio sin sobrescribir nada, SHALL aplicarlo a las siguientes validaciones sin reiniciar y SHALL registrar un `admin_event` con la huella.

#### Scenario: Ancla válida
- **WHEN** se agrega una raíz vigente
- **THEN** responde `201`, aparece en el listado y una cadena que antes no era de confianza pasa a serlo

#### Scenario: Certificado inválido
- **WHEN** el contenido no es un certificado, está vencido, o es un certificado final que no es CA ni autofirmado
- **THEN** responde `422` y no cambia el directorio

#### Scenario: Ancla repetida
- **WHEN** ya existe un ancla con la misma huella
- **THEN** responde `409`

#### Scenario: Varios certificados
- **WHEN** el PEM contiene más de un certificado
- **THEN** responde `422`

### Requirement: Quitar un ancla de confianza
`DELETE /api/v1/admin/trust-anchors/{fingerprint}` SHALL quitar esa ancla, SHALL aplicarlo a las siguientes validaciones y SHALL registrar un `admin_event`. SHALL rechazar con `409` quitar un ancla cuyo archivo contenga otros certificados.

#### Scenario: Ancla quitada
- **WHEN** se quita un ancla
- **THEN** una cadena que dependía de ella deja de ser de confianza en la siguiente validación y los documentos ya firmados no cambian

#### Scenario: Huella inexistente
- **WHEN** la huella no corresponde a ningún ancla
- **THEN** responde `404`

### Requirement: Rotación del certificado propio
`POST /api/v1/admin/local-certificate/rotate` SHALL archivar el certificado público vigente del proveedor `local`, destruir su clave privada, generar un par nuevo, aplicar el cambio a las siguientes firmas y registrar un `admin_event`. `GET /api/v1/admin/local-certificate` SHALL mostrar el certificado vigente y los archivados.

#### Scenario: Rotación
- **WHEN** se rota el certificado propio
- **THEN** las nuevas firmas usan el certificado nuevo, la clave vieja ya no existe en disco y existe un `admin_event`

#### Scenario: Firmas anteriores
- **WHEN** se verifica un documento firmado antes de la rotación
- **THEN** su firma sigue siendo válida y de confianza

#### Scenario: Sin certificado previo
- **WHEN** el proveedor aún no generó su certificado
- **THEN** la rotación genera uno nuevo sin archivar nada
