# Widget Session Specification

## Purpose

Credencial acotada del widget (token HMAC por solicitud), endpoints del widget y entrega segura de la página con protección contra clickjacking.

## Requirements

### Requirement: Token del widget acotado a una solicitud
El servidor SHALL emitir, para cada solicitud de firma, un token firmado con HMAC-SHA256 que identifique **una sola** solicitud y venza a los `FIRMADOC_SIGNING_TOKEN_TTL_SECONDS` (3600 por defecto), y SHALL rechazar con `401` todo token manipulado, vencido, de otra solicitud o firmado con otro secreto.

#### Scenario: Token válido
- **WHEN** se invoca un endpoint del widget con el token emitido para esa solicitud
- **THEN** el pedido se procesa

#### Scenario: Token de otra solicitud
- **WHEN** se usa el token de la solicitud A sobre la solicitud B
- **THEN** la respuesta es `401`

#### Scenario: Token vencido o alterado
- **WHEN** el token venció o se modificó un solo carácter
- **THEN** la respuesta es `401`

#### Scenario: Sin token
- **WHEN** falta la cabecera `Authorization: Bearer <token>`
- **THEN** la respuesta es `401`

### Requirement: El token no abre la API de integración
El token del widget SHALL habilitar únicamente los endpoints del widget y SHALL NOT ser aceptado por los endpoints de `/api/v1/signature-requests` ni de `/api/v1/documents`, que siguen exigiendo `X-API-Key`.

#### Scenario: Token usado como API key
- **WHEN** se envía el token del widget como `X-API-Key` o como `Bearer` a un endpoint de integración
- **THEN** la respuesta es `401`

### Requirement: Secreto de firma configurable
El secreto de los tokens SHALL leerse de `FIRMADOC_SIGNING_SECRET` (mínimo 32 caracteres); si no está configurado el servidor SHALL generar uno efímero al arrancar y advertirlo en el registro, porque los tokens dejan de valer al reiniciar.

#### Scenario: Secreto demasiado corto
- **WHEN** `FIRMADOC_SIGNING_SECRET` tiene menos de 32 caracteres
- **THEN** el servidor no arranca y explica el motivo

#### Scenario: Sin secreto configurado
- **WHEN** no hay secreto configurado
- **THEN** el servidor arranca con uno efímero y registra una advertencia

### Requirement: Contexto de la solicitud para el widget
`GET /api/v1/widget/requests/{id}` SHALL devolver lo necesario para dibujar la interfaz sin exponer datos del integrador: estado, proveedor, nombre del documento, nombre del firmante, `allowed_origins` del integrador, `agent_url`, vencimiento del token y, si ya está firmada, el bloque `document` sin el binario.

#### Scenario: Solicitud pendiente
- **WHEN** el widget consulta el contexto de una solicitud `pending`
- **THEN** la respuesta incluye `status`, `provider`, `document_name`, `signer_name`, `allowed_origins` y `agent_url`

#### Scenario: Datos que no se exponen
- **WHEN** se consulta el contexto
- **THEN** la respuesta no incluye la API key, su hash ni datos de otros documentos o solicitudes

### Requirement: Preparar y completar desde el widget
`POST /api/v1/widget/requests/{id}/prepare` y `.../complete` SHALL aplicar exactamente las mismas reglas del flujo de integración (validación del certificado, desafíos de un solo uso, verificación de la firma, versionado), con los mismos códigos de error, y SHALL atar el desafío a la sesión indicada en la cabecera `X-Session-Ref`.

#### Scenario: Flujo token desde el widget
- **WHEN** el widget envía un certificado válido a `prepare` y luego las firmas del agente a `complete`
- **THEN** la solicitud pasa a `signed` y se crea la nueva versión vigente

#### Scenario: Certificado rechazado
- **WHEN** el certificado está revocado o su CUIL no coincide
- **THEN** la respuesta lleva el mismo `code` (`certificate_revoked`, `cuil_mismatch`, …) que en la API de integración

#### Scenario: Otra sesión
- **WHEN** `complete` llega con un `X-Session-Ref` distinto del de `prepare`
- **THEN** la respuesta es `409`

### Requirement: Descarga del documento firmado desde el widget
`GET /api/v1/widget/requests/{id}/download` SHALL devolver el PDF de la versión generada por esa solicitud, solo cuando esa solicitud está `signed`.

#### Scenario: Descarga tras firmar
- **WHEN** la solicitud está `signed` y se invoca la descarga con su token
- **THEN** la respuesta es `200` con `application/pdf` y el PDF firmado

#### Scenario: Descarga antes de firmar
- **WHEN** la solicitud todavía no está `signed`
- **THEN** la respuesta es `409`

### Requirement: Página del widget con protección contra clickjacking
`GET /sign/{id}` SHALL servir el widget compilado con `Content-Security-Policy: frame-ancestors` igual a los `allowed_origins` del sistema integrador de esa solicitud (o `'none'` si no tiene ninguno), `Referrer-Policy: no-referrer` y `Cache-Control: no-store`, sin requerir el token (que viaja en el fragmento de la URL y no llega al servidor).

#### Scenario: Origen permitido
- **WHEN** se solicita `/sign/{id}` de una solicitud cuyo integrador permite `https://gestor.example.org`
- **THEN** la respuesta lleva `frame-ancestors https://gestor.example.org`

#### Scenario: Integrador sin orígenes
- **WHEN** el integrador no tiene orígenes permitidos
- **THEN** la respuesta lleva `frame-ancestors 'none'`

#### Scenario: Solicitud inexistente
- **WHEN** el identificador no corresponde a ninguna solicitud
- **THEN** la respuesta es `404` sin cabeceras de widget ni detalle

### Requirement: Recursos estáticos del widget
El servidor SHALL servir los archivos compilados del widget desde `FIRMADOC_WIDGET_DIST` bajo `/widget-assets/` y `widget.js` en `/widget.js`, y SHALL arrancar sin ellos (los endpoints de la API siguen funcionando) cuando el directorio no existe.

#### Scenario: Widget compilado
- **WHEN** existe el directorio compilado
- **THEN** `/widget-assets/*` y `/widget.js` se sirven con tipos de contenido correctos

#### Scenario: Sin compilar
- **WHEN** el directorio no existe
- **THEN** `GET /sign/{id}` responde `503` con un mensaje claro y la API de integración no se ve afectada
