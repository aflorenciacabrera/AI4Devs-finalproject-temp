# pdf-upload-signing Specification

## Purpose
TBD - created by archiving change carga-de-pdf-y-seccion-firmar. Update Purpose after archive.

## Requirements

### Requirement: Carga de PDF desde el panel
`POST /api/v1/admin/signing-uploads` SHALL aceptar, con el token de administración, un JSON con `filename`, `document_base64` y opcionalmente `signer` (nombre completo, identificador y correo). SHALL validar el PDF con el mismo motor y el mismo tamaño máximo (`max_document_bytes`) que la API de integradores, guardarlo como versión original v1 y crear la solicitud de firma, y SHALL responder `201` con `request_id`, `document_id`, `signing_url`, `filename`, `page_count`, `size_bytes` y `document_hash`.

#### Scenario: Carga válida
- **WHEN** se envía un PDF válido con el token de administración
- **THEN** se crea el documento con una versión v1 de origen subido, se crea una solicitud de firma pendiente y se devuelve la `signing_url` del widget

#### Scenario: Archivo que no es PDF
- **WHEN** `document_base64` no es base64 válido o no es un PDF legible
- **THEN** responde `422` y no se crea documento, versión ni solicitud

#### Scenario: Excede el tamaño
- **WHEN** el PDF supera `max_document_bytes`
- **THEN** responde `422` y no se guarda nada

#### Scenario: Sin credenciales
- **WHEN** falta el token de administración o es inválido
- **THEN** responde `401`; con la administración deshabilitada responde `404`

### Requirement: Sistema integrador interno del panel
Los documentos cargados desde el panel SHALL pertenecer a un sistema integrador reservado llamado «Firmadoc (panel)», creado la primera vez que se necesita. Sus orígenes permitidos SHALL ser el origen de `public_base_url` más los de `FIRMADOC_PANEL_ORIGINS` (lista separada por comas, vacía por defecto; pensada para el servidor de desarrollo del panel Angular), y SHALL sincronizarse con la configuración vigente en cada carga desde el panel. Su API key SHALL generarse al azar y no mostrarse nunca, de modo que no pueda usarse en la API de integradores.

#### Scenario: Creación diferida
- **WHEN** se hace la primera carga desde el panel
- **THEN** se crea el sistema interno; las cargas siguientes lo reutilizan sin duplicarlo

#### Scenario: Orígenes extra para el servidor de desarrollo
- **WHEN** `FIRMADOC_PANEL_ORIGINS=http://localhost:4200` y se carga un PDF desde el panel
- **THEN** la página del widget de esa solicitud responde `frame-ancestors` con el origen de `public_base_url` y `http://localhost:4200`

#### Scenario: Cambio de configuración
- **WHEN** el sistema interno ya existía con otros orígenes y cambia la configuración
- **THEN** la siguiente carga desde el panel actualiza sus orígenes permitidos sin duplicar el sistema

#### Scenario: Sin acceso por API key
- **WHEN** alguien intenta autenticarse en la API de integradores con cualquier clave contra ese sistema
- **THEN** responde `401`

### Requirement: Firmante y método de la solicitud
Si no se informa `signer`, la solicitud SHALL registrar como firmante a «Operador del panel». La solicitud SHALL permitir elegir en el widget todos los métodos habilitados en el servidor, usando como método inicial el primero disponible en el orden `token`, `firmar`, `local`.

#### Scenario: Firmante por defecto
- **WHEN** se carga un PDF sin `signer`
- **THEN** la solicitud queda con el firmante «Operador del panel» y la firma completada refleja el sujeto del certificado usado

#### Scenario: Métodos
- **WHEN** el servidor está en modo real (el proveedor `local` no se admite)
- **THEN** la solicitud no ofrece `local` y el widget solo ofrece los demás métodos habilitados

### Requirement: Auditoría de la carga
Cada carga SHALL registrar un evento de auditoría de administración con el documento, el nombre de archivo y el hash, sin contener el contenido del PDF.

#### Scenario: Evento registrado
- **WHEN** se completa una carga válida
- **THEN** existe un evento de auditoría que referencia el documento y el hash

### Requirement: Carga de varios PDF desde el panel
`POST /api/v1/admin/signing-batch-uploads` SHALL aceptar, con el token de administración, `documents` (de 2 a `max_batch_size`, cada uno con `filename` y `document_base64`) y `signer` opcional, validar todos los PDF con las mismas reglas que la carga individual, guardarlos como versión original v1 y crear **un lote** en el sistema integrador interno del panel con los métodos `token` y `local` según estén habilitados. SHALL responder `201` con `batch_id`, `signing_url` de lote y, por documento, `document_id`, `filename`, `page_count`, `size_bytes` y `document_hash`. Es atómico: si uno es inválido no se crea nada (`422`).

#### Scenario: Lote válido
- **WHEN** se envían 3 PDF válidos con el token de administración
- **THEN** se crean 3 documentos con versión v1 y un lote con 3 solicitudes pendientes, y se devuelve la `signing_url` de lote

#### Scenario: Un archivo inválido
- **WHEN** uno de los archivos no es un PDF legible
- **THEN** responde `422` y no se crea ningún documento, versión, solicitud ni lote

#### Scenario: Cantidad fuera de rango
- **WHEN** se envían menos de 2 o más de `max_batch_size` documentos
- **THEN** responde `422`

#### Scenario: Auditoría
- **WHEN** se crea el lote
- **THEN** queda un evento de administración `panel_batch_upload` con los documentos y hashes, sin contenido
