# angular-panel Specification

## Purpose
TBD - created by archiving change panel-angular-primeng. Update Purpose after archive.

## Requirements

### Requirement: Panel Angular con PrimeNG
El repositorio SHALL incluir en `frontend/` una aplicación Angular (componentes standalone, sin zone.js, sin enrutador) con PrimeNG, en español, que consuma la API de administración y ofrezca, en un menú lateral de PrimeNG, las mismas secciones que el panel estático: ingreso con token, Firmar documento, Documentos (listado con búsqueda, filtros, paginación, origen, versión y vencimiento; detalle con línea de tiempo, versiones descargables y detalle técnico), Auditoría (entregas de webhook con reenvío y eventos de administración), Integradores (alta con credenciales mostradas una sola vez, edición de orígenes, rotación de secreto y de API key, habilitar y deshabilitar) y Confianza (anclas: agregar y quitar; certificado propio: rotar). SHALL pedir confirmación en un diálogo antes de reenviar un webhook, quitar un ancla, rotar el certificado, rotar claves de un integrador o deshabilitarlo. El token SHALL guardarse solo en memoria y en `sessionStorage` y enviarse en `Authorization: Bearer`; una respuesta `401` SHALL cerrar la sesión con un mensaje claro. El modo claro/oscuro SHALL seguir al sistema hasta que la persona elija y la elección SHALL recordarse en el navegador.

#### Scenario: Ingreso y secciones
- **WHEN** la persona ingresa un token válido
- **THEN** ve la navegación con todas las secciones y «Firmar documento» activa

#### Scenario: Token inválido
- **WHEN** el token es rechazado con `401`
- **THEN** se muestra «Acceso denegado» y no se guarda el token

#### Scenario: Confirmación antes de una acción destructiva
- **WHEN** pulsa «Rotar certificado»
- **THEN** no se rota hasta confirmar en el diálogo

### Requirement: Carga de documentos y widget embebido en Angular
La sección «Firmar documento» SHALL usar el componente de carga de PrimeNG para elegir o arrastrar uno o varios PDF, rechazar en el navegador los archivos que no sean PDF o superen el tamaño máximo (sin enviar nada), listar los archivos elegidos con «Quitar» por archivo y ofrecer «Cargar y firmar» (con la cantidad cuando hay varios). Al confirmar SHALL enviar un archivo a `POST /api/v1/admin/signing-uploads` o varios a `POST /api/v1/admin/signing-batch-uploads`, mostrar la tarjeta del documento (nombre, páginas, tamaño) o la lista del lote y el aviso de versiones, y abrir el widget con la `signing_url` devuelta en una **ventana propia** (`window.open`, reservada en el gesto del usuario antes de subir el archivo, para que el navegador no la bloquee; Firmadoc es la página principal de esa ventana, sin módulo dentro de un diálogo ni delegación del permiso de red local). Si el navegador bloquea la ventana, SHALL abrir el widget en un diálogo con un `iframe` con `sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-popups-to-escape-sandbox"`, `allow="local-network-access; local-network; loopback-network"` y `referrerpolicy="no-referrer"`. SHALL aceptar los mensajes del widget solo si vienen de la ventana abierta (o de la ventana del iframe) y del origen de la `signing_url`, mostrar el resultado (firmado, lote «N de M», fallido, cancelado), ofrecer «Ir a la ventana de firma» mientras esté abierta y, si se cierra sin firmar, avisarlo. «Quitar» y «Reemplazar» SHALL volver a la carga cerrando la ventana o el diálogo.

#### Scenario: Un PDF
- **WHEN** elige un PDF válido y pulsa «Cargar y firmar»
- **THEN** se muestra la tarjeta del documento y el widget se abre en una ventana propia con la `signing_url`

#### Scenario: Varios PDF
- **WHEN** elige tres PDF válidos y confirma
- **THEN** se envían como lote y se muestra la lista de los tres y el widget de lote en la ventana propia

#### Scenario: Archivo inválido
- **WHEN** entre los archivos hay uno que no es PDF
- **THEN** se indica cuál es y no se envía nada

#### Scenario: Mensaje de otra ventana u origen
- **WHEN** llega un `message` que no proviene de la ventana abierta (o de la ventana del iframe) o de su origen
- **THEN** se ignora

#### Scenario: Ventana bloqueada
- **WHEN** el navegador bloquea la ventana emergente
- **THEN** el widget se abre en el diálogo con el iframe, con los mismos resultados en la tarjeta

#### Scenario: Ventana cerrada sin firmar
- **WHEN** la persona cierra la ventana (o el widget la cierra con «Cerrar») sin haber firmado
- **THEN** la tarjeta avisa que el documento quedó sin firmar y permite abrir el módulo de nuevo

### Requirement: Servido del panel Angular
`GET /panel` SHALL servir el `index.html` del build de Angular (`FIRMADOC_FRONTEND_DIST`, por defecto `frontend/dist/firmadoc-panel/browser`) y `GET /panel/{archivo}` sus recursos, solo archivos existentes dentro del directorio del build. SHALL responder `404` si la administración está deshabilitada y `503` con `code: frontend_not_built` si el build no existe. La página SHALL llevar la misma política de seguridad de contenido que el panel estático (`default-src 'none'`, `script-src 'self'`, `connect-src 'self'`, `frame-src 'self'`, `frame-ancestors 'none'`, sin caché), salvo `base-uri 'self'` (el build lleva `<base href="/panel/">`), y, en `style-src`, un nonce aleatorio por pedido que el servidor SHALL insertar en el atributo `ngCspNonce` del `index.html` para los estilos que Angular y PrimeNG inyectan; el build SHALL NOT incrustar estilos en línea sin nonce.

#### Scenario: Página disponible
- **WHEN** hay token de administración y el build existe
- **THEN** `/panel` responde `200` con la CSP, `style-src 'self' 'nonce-…'` y el mismo nonce dentro del HTML

#### Scenario: Nonce distinto por pedido
- **WHEN** se pide `/panel` dos veces
- **THEN** cada respuesta lleva un nonce diferente

#### Scenario: Build ausente
- **WHEN** no existe el `index.html` del build
- **THEN** `/panel` responde `503` con `code: frontend_not_built`

#### Scenario: Deshabilitado o fuera del directorio
- **WHEN** no hay token configurado, o se pide un archivo inexistente o con `..`
- **THEN** responde `404`
