## ADDED Requirements

### Requirement: Credencial y página del lote
El token del widget SHALL poder emitirse para un lote usando el identificador del lote, con el mismo formato y la misma vida corta que el de una solicitud. `GET /sign/batch/{batch_id}` SHALL servir la página del widget con las mismas cabeceras de seguridad que `/sign/{id}` (`frame-ancestors` con los orígenes permitidos del sistema integrador dueño del lote) y SHALL responder `404` sin detalle si el lote no existe. Un token emitido para un lote SHALL NOT abrir los endpoints de una solicitud ni los de otro lote, ni al revés.

#### Scenario: Página del lote
- **WHEN** se pide `/sign/batch/{id}` de un lote existente
- **THEN** responde `200` con la página del widget y `frame-ancestors` con los orígenes del integrador

#### Scenario: Lote inexistente
- **WHEN** se pide `/sign/batch/{id}` con un id que no existe
- **THEN** responde `404` sin cabeceras de widget

#### Scenario: Token cruzado
- **WHEN** se usa el token de un lote contra `/api/v1/widget/requests/{id}` o contra otro lote
- **THEN** responde `401` con el código `invalid_token`

### Requirement: Endpoints del widget para lotes
Bajo `/api/v1/widget/batches/{batch_id}`, autenticados solo con el token del lote, SHALL existir: `GET` (contexto del lote), `POST /provider` (elegir método), `POST /prepare`, `POST /complete`, `GET /download` y `POST /retry`. SHALL reutilizar los casos de uso de `signature_batch` y NO SHALL aceptar la API key de integrador. El contexto SHALL incluir el estado del lote, el método, los métodos permitidos, el firmante, los orígenes permitidos, la URL del agente, el vencimiento del token y, por documento, `signature_request_id`, `document_id`, nombre, páginas, tamaño, estado, número de versión y error si lo hubo, sin binarios ni token.

#### Scenario: Contexto
- **WHEN** el widget pide el contexto con un token válido
- **THEN** recibe el lote con un ítem por documento (nombre, páginas y tamaño) y sin ningún PDF

#### Scenario: Sin credenciales válidas
- **WHEN** falta el token, está vencido o está alterado
- **THEN** responde `401` con `invalid_token`

### Requirement: Un certificado y un PIN por lote
Con el método `token`, el widget SHALL elegir y validar el certificado una sola vez para todo el lote, pedir al agente la firma de todos los hashes del lote en una única llamada (un solo PIN) y enviar todas las firmas en un único `complete`. Con `local`, SHALL completar el lote sin firmas del agente.

#### Scenario: Un PIN para N documentos
- **WHEN** la persona confirma «Firmar N documentos» con el token
- **THEN** el agente recibe N desafíos en una sola llamada, el PIN se pide una vez y `complete` se envía una vez con las N firmas

#### Scenario: Certificado rechazado
- **WHEN** el servidor rechaza el certificado al preparar el lote
- **THEN** no se pide el PIN y se muestra el rechazo con su motivo, igual que en la firma individual

### Requirement: Revisión del lote
El widget SHALL mostrar, antes de firmar, la lista de documentos del lote (nombre, páginas y tamaño), la elección de método y el botón «Firmar N documentos». Con un solo método permitido, la revisión SHALL mostrar su tarjeta ya seleccionada.

#### Scenario: Lista de documentos
- **WHEN** se abre el widget de un lote de 3 documentos
- **THEN** se listan los 3 con su nombre, páginas y tamaño y el botón dice «Firmar 3 documentos»

#### Scenario: Firma remota no disponible
- **WHEN** el método `firmar` aparece entre las tarjetas de un lote
- **THEN** se muestra deshabilitado, con el aviso de que el servicio puede limitar la cantidad de documentos por lote y de que no está disponible para lotes

### Requirement: Resultado parcial y descarga
Al terminar, el widget SHALL mostrar «N de M documentos firmados», el estado de cada documento (versión firmada o el motivo del error de la respuesta de `complete`) y el botón «Descargar firmados (N)». `GET /api/v1/widget/batches/{id}/download` SHALL devolver un ZIP con los PDF vigentes de los documentos firmados del lote (sin binarios de los demás), con `Cache-Control: no-store`, y `409` si ninguno está firmado.

#### Scenario: Éxito parcial
- **WHEN** 2 de 3 documentos se firman y 1 falla
- **THEN** se muestra «2 de 3 documentos firmados», cada ítem con su estado y el error del fallido, y «Descargar firmados (2)»

#### Scenario: Descarga
- **WHEN** la persona descarga los firmados
- **THEN** recibe un ZIP con solo los 2 PDF firmados

#### Scenario: Nada firmado
- **WHEN** se pide la descarga de un lote sin documentos firmados
- **THEN** responde `409`

### Requirement: Reintento de los fallidos
`POST /api/v1/widget/batches/{id}/retry` SHALL crear otro lote con los `document_id` de los documentos fallidos, del mismo sistema, firmante y método permitidos, y devolver el id y la `signing_url` del nuevo lote; los documentos ya firmados NO SHALL volver a firmarse. SHALL responder `409` si el lote no tiene documentos fallidos o no está terminado. El widget SHALL ofrecer «Reintentar» por documento fallido y pasar al nuevo lote.

#### Scenario: Reintentar el fallido
- **WHEN** se reintenta un lote con 1 documento fallido y 2 firmados
- **THEN** se crea un lote nuevo solo con el fallido y el widget pasa a su revisión

#### Scenario: Sin fallidos
- **WHEN** se pide reintentar un lote completamente firmado
- **THEN** responde `409`

### Requirement: Mensajes al anfitrión del lote
Al terminar, el widget SHALL enviar al anfitrión un `postMessage` `firmadoc:batch-completed` con el id del lote, el estado, la cantidad firmada y total y, por documento, `document_id`, estado y versión; SHALL NOT incluir PDF, firmas ni el token. Seguirán enviándose `firmadoc:ready`, `firmadoc:cancelled` y `firmadoc:closed`, solo a los orígenes permitidos.

#### Scenario: Resultado del lote
- **WHEN** el lote termina
- **THEN** el anfitrión recibe `firmadoc:batch-completed` con los conteos y los estados, sin datos sensibles
