## ADDED Requirements

### Requirement: Varios PDF en «Firmar documento»
La sección «Firmar documento» SHALL aceptar uno o varios PDF. Con uno, mantiene el comportamiento de carga individual; con más de uno, SHALL listar los archivos cargados (nombre, páginas y tamaño, con «Quitar» por archivo), enviarlos con `POST /api/v1/admin/signing-batch-uploads` y embeber el widget de lote con la `signing_url` devuelta. Los archivos que no sean PDF SHALL rechazarse en el navegador sin enviar nada, y SHALL aplicarse el máximo de documentos por lote.

#### Scenario: Varios PDF
- **WHEN** la persona selecciona 3 PDF válidos
- **THEN** se listan los 3 con nombre, páginas y tamaño y se muestra el widget de lote «Firmar 3 documentos»

#### Scenario: Mezcla con un archivo inválido
- **WHEN** entre los archivos hay uno que no es PDF
- **THEN** no se envía nada y se indica cuál es

#### Scenario: Resultado del lote
- **WHEN** el widget informa `firmadoc:batch-completed`
- **THEN** la sección muestra «N de M documentos firmados» y permite cargar otros
