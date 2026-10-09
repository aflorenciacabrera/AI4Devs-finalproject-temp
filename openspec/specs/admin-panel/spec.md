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

### Requirement: Navegación lateral y estilo
El panel SHALL ofrecer una barra lateral con las secciones «Firmar documento», «Documentos», «Auditoría», «Integradores» y «Confianza» (con la sección activa marcada y navegable con teclado), en lugar de pestañas. «Auditoría» SHALL reunir las entregas de webhook y los eventos de administración; «Confianza» SHALL reunir las anclas de confianza y el certificado propio. Se mantienen las reglas de seguridad de la página (CSP sin scripts ni estilos en línea, contenido como texto, token en `sessionStorage`) y el modo claro/oscuro.

#### Scenario: Cambiar de sección
- **WHEN** se elige «Integradores» en la barra lateral
- **THEN** se muestra esa sección y queda marcada como activa

#### Scenario: Secciones agrupadas
- **WHEN** se abre «Confianza»
- **THEN** se ven las anclas de confianza y el certificado propio

### Requirement: Listado de documentos
«Documentos» SHALL mostrar el listado con las columnas Documento (nombre y `vN`), Firmante, Fecha, Proveedor, Origen («Individual» o «Lote #…» con las filas de un lote contiguas), Estado en español con color (Firmado, Pendiente con su vencimiento, Firmando, Fallido) y Acciones; con búsqueda por documento o firmante y filtros por estado, proveedor, origen y fechas, y paginación.

#### Scenario: Origen y vencimiento
- **WHEN** hay un documento firmado en lote y uno pendiente con fecha límite
- **THEN** el primero muestra «Lote #…» y el segundo «Individual» con «Vence dd/mm/aaaa»

#### Scenario: Texto hostil
- **WHEN** un nombre de documento o firmante contiene HTML
- **THEN** se muestra como texto y no se ejecuta

### Requirement: Detalle del documento
Al elegir un documento SHALL mostrarse su detalle con «Volver a Documentos», nombre, ID externo, estado, descarga del firmado vigente, la **línea de tiempo** de la cadena de custodia (hora, actor, título y detalle), la tarjeta **Versiones** (la vigente marcada, con descarga de cada versión) y el **Detalle técnico**; sin mostrar IP de origen, hashes a firmar ni secretos.

#### Scenario: Ver la historia
- **WHEN** se abre el detalle de un documento firmado
- **THEN** se ve la línea de tiempo en orden, las versiones v1 y v2 con la v2 vigente y el detalle técnico

#### Scenario: Descargar una versión
- **WHEN** se elige «Descargar» en la v1
- **THEN** se baja el PDF original sin firmar

### Requirement: Pantalla de Integradores
«Integradores» SHALL listar los sistemas (nombre, orígenes permitidos, estado y si es interno) y permitir crear uno, editar sus orígenes, rotar su secreto de webhook, rotar su API key y deshabilitarlo o habilitarlo, con confirmación en las acciones que invalidan credenciales. La API key y el secreto en claro SHALL mostrarse una sola vez tras crear o rotar, con aviso de que no se vuelven a mostrar, y NO SHALL guardarse en el navegador. El sistema interno SHALL figurar sin acciones.

#### Scenario: Alta con credenciales de una sola vez
- **WHEN** se crea un integrador
- **THEN** se muestran su API key y su secreto de webhook con el aviso de guardarlos, y al volver al listado ya no aparecen

#### Scenario: Rotar con confirmación
- **WHEN** se elige «Rotar API key» y se cancela la confirmación
- **THEN** no se rota nada
