# admin-panel Specification

## Purpose
TBD - created by archiving change panel-de-administracion. Update Purpose after archive.

## Requirements

### Requirement: Página de administración
`GET /admin` SHALL servir una página web propia (HTML, CSS y JavaScript sin dependencias externas) con secciones para solicitudes, custodia de un documento, webhooks, anclas de confianza, certificado propio y eventos de administración, que consume la API de administración. SHALL responder `404` si la administración está deshabilitada.

#### Scenario: Página disponible
- **WHEN** hay token de administración configurado
- **THEN** `/admin` responde `200` con la página y sus recursos estáticos

#### Scenario: Deshabilitada
- **WHEN** no hay token configurado
- **THEN** `/admin` y sus recursos responden `404`

### Requirement: Seguridad de la página
La página SHALL servirse con una política de seguridad de contenido que solo permita recursos del propio origen (incluido `frame-src 'self'` para el widget embebido), sin scripts ni estilos en línea, SHALL prohibir ser embebida (`frame-ancestors 'none'`), SHALL no cachearse y SHALL construir el contenido con `textContent` (nunca `innerHTML`). El token SHALL guardarse en `sessionStorage` y enviarse solo en `Authorization`; la página SHALL NOT usar cookies. El iframe del widget SHALL crearse con `sandbox="allow-scripts allow-same-origin allow-downloads"` y `referrerpolicy="no-referrer"`.

#### Scenario: Cabeceras
- **WHEN** se solicita `/admin`
- **THEN** la respuesta lleva la CSP restrictiva con `frame-src 'self'` y `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff` y `Cache-Control: no-store`

#### Scenario: Contenido hostil
- **WHEN** un dato mostrado contiene etiquetas HTML o scripts (por ejemplo un nombre de archivo)
- **THEN** se muestra como texto y no se ejecuta

### Requirement: Uso del panel
El panel SHALL pedir el token de administración, SHALL informar con claridad un token inválido, SHALL permitir cerrar sesión borrando el token, y SHALL pedir confirmación antes de reenviar un webhook, quitar un ancla o rotar el certificado.

#### Scenario: Ingreso y listado
- **WHEN** se ingresa un token válido
- **THEN** se ve el listado de solicitudes y se pueden aplicar filtros

#### Scenario: Token inválido
- **WHEN** se ingresa un token incorrecto
- **THEN** se muestra un mensaje de acceso denegado y no se guarda el token

#### Scenario: Confirmación
- **WHEN** se pulsa "Rotar certificado"
- **THEN** no se rota hasta confirmar

### Requirement: Sección «Firmar documento»
El panel SHALL incluir una sección «Firmar documento» que permita soltar o seleccionar un PDF, mostrar una tarjeta con nombre, páginas y tamaño con acciones «Reemplazar» y «Quitar», informar que se guarda como versión original (v1) y que la firmada será la v2 vigente, y mostrar los pasos «Cómo se firma». Al confirmar SHALL cargar el PDF con `POST /api/v1/admin/signing-uploads` y mostrar el widget embebido con la `signing_url` devuelta. La sección SHALL aceptar un solo archivo; un archivo que no sea PDF SHALL rechazarse en el navegador con un mensaje claro.

#### Scenario: Carga y vista previa
- **WHEN** la persona selecciona un PDF válido
- **THEN** se muestra la tarjeta del documento con su nombre, páginas y tamaño y el aviso de versiones

#### Scenario: Reemplazar o quitar
- **WHEN** elige «Quitar» o «Reemplazar»
- **THEN** vuelve a la zona de carga sin widget; el documento ya cargado queda guardado en el servidor pero sin firmarse

#### Scenario: Archivo no PDF
- **WHEN** selecciona un archivo que no es PDF
- **THEN** no se envía nada al servidor y se muestra el error

### Requirement: Resultado de la firma en la sección
La sección SHALL escuchar los mensajes del widget y, solo si provienen del origen del propio servidor y de la ventana del iframe, mostrar el resultado: documento firmado con enlace de descarga, firma cancelada o firma fallida, y permitir cargar otro documento.

#### Scenario: Firma completada
- **WHEN** el widget envía `firmadoc:signed`
- **THEN** la sección muestra que el documento quedó firmado como nueva versión vigente y ofrece descargarlo

#### Scenario: Mensaje de otro origen
- **WHEN** llega un `postMessage` desde un origen o una ventana distintos al iframe del widget
- **THEN** se ignora
