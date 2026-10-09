## ADDED Requirements

### Requirement: Nombre de archivo en las descargas
Toda descarga de un PDF (`GET /api/v1/documents/{id}/versions/{n}/download`, `GET /api/v1/widget/requests/{id}/download`, `GET /api/v1/admin/documents/{id}/versions/{n}/download`) SHALL sugerir como nombre de archivo el nombre original del documento: su `external_document_id` (el panel registra ahí el nombre del archivo cargado, sin `.pdf`) con la extensión `.pdf` una sola vez, o el id del documento si no tiene identificador. El nombre SHALL conservar acentos, espacios y paréntesis y SHALL NOT llevar sufijo de versión; los separadores de ruta (`/`, `\`) SHALL reemplazarse por `_` y los caracteres de control y las comillas SHALL quitarse. La cabecera `Content-Disposition` SHALL incluir `filename` (latin-1) y `filename*` (UTF-8). Dentro del ZIP de un lote, cada PDF SHALL llevar ese mismo nombre y, si dos coinciden, el segundo y siguientes SHALL llevar `-2`, `-3`… antes de la extensión. Ese nombre SHALL ser también el que muestra el widget y el que recibe el agente.

#### Scenario: Descarga con el nombre original
- **WHEN** se cargó `Resolución 450 (nueva).pdf` desde el panel, se firmó, y se descarga la versión firmada desde el widget, la API o el panel
- **THEN** el archivo sugerido se llama `Resolución 450 (nueva).pdf`, tanto para la versión 1 como para la 2

#### Scenario: Nombre con caracteres peligrosos
- **WHEN** el identificador externo contiene comillas, saltos de línea o barras
- **THEN** la cabecera no los contiene y la descarga responde `200`

#### Scenario: ZIP con nombres repetidos
- **WHEN** un lote firmado tiene dos documentos llamados `acta.pdf`
- **THEN** el ZIP contiene `acta.pdf` y `acta-2.pdf`
