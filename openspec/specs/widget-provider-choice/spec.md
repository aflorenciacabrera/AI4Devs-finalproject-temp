# widget-provider-choice Specification

## Purpose
TBD - created by archiving change eleccion-de-proveedor-en-el-widget. Update Purpose after archive.

## Requirements

### Requirement: Pantalla de elección del método
Cuando la solicitud está `pending` y tiene más de un método disponible, el widget SHALL abrir en una pantalla "¿Cómo querés firmar?" que lista cada método con su nombre y una descripción (firma digital con token, firma electrónica de demostración, firma con servicio remoto), SHALL permitir elegir uno y cancelar, y SHALL no tocar la red local ni consultar al agente hasta que se elija el token.

#### Scenario: Varios métodos
- **WHEN** el contexto trae `allowed_providers` con dos o más métodos y estado `pending`
- **THEN** se muestra la elección y no se consulta al agente

#### Scenario: Un solo método
- **WHEN** hay un único método disponible
- **THEN** se salta la elección y se sigue el flujo de ese método, como hasta ahora

#### Scenario: Elegir token
- **WHEN** la persona elige el método con token
- **THEN** se confirma la elección en el servidor y recién entonces se detecta el agente

#### Scenario: Error al elegir
- **WHEN** el servidor rechaza la elección
- **THEN** se muestra un mensaje claro y se puede volver a intentar o cancelar

### Requirement: Volver a elegir otro método
Mientras no se haya preparado la firma, las pantallas de espera o error del widget (agente no encontrado, problema del agente, elegir certificado, certificado rechazado, confirmar firma de demostración y confirmar firma remota) SHALL ofrecer "Elegir otro método" cuando la solicitud tiene más de un método disponible, y ese botón SHALL volver a la pantalla de elección.

#### Scenario: Agente no encontrado
- **WHEN** no se detecta el agente y hay otro método disponible
- **THEN** la pantalla ofrece "Elegir otro método"

#### Scenario: Un solo método
- **WHEN** la solicitud solo permite un método
- **THEN** no se muestra "Elegir otro método"

#### Scenario: Firma en curso
- **WHEN** se está esperando el PIN, completando la firma o esperando al servicio remoto
- **THEN** no se ofrece cambiar de método

### Requirement: Firma remota desde el widget
Con el proveedor `firmar`, el widget SHALL mostrar una pantalla de confirmación, enviar el documento al servicio con `prepare`, mostrar el enlace "Continuar en el servicio de firma" (nunca abierto automáticamente) y consultar el estado de la solicitud periódicamente hasta que sea `signed` o `failed`, mostrando entonces la firma completada o el error y notificando al sistema anfitrión como en los demás métodos. Al pulsar el enlace, el widget SHALL abrir el servicio en una ventana emergente acotada y centrada sobre la del panel; si el navegador la bloquea, el enlace SHALL abrirse en una pestaña (`target="_blank"` con `rel="noreferrer"`). Cuando la espera termina (firmada, rechazada, vencida o cancelada) el widget SHALL cerrar esa ventana si sigue abierta.

#### Scenario: Firma remota exitosa
- **WHEN** el servicio informa la firma y la solicitud pasa a `signed`
- **THEN** el widget muestra la firma completada, cierra la ventana del servicio y notifica `signed` al anfitrión

#### Scenario: Rechazo del servicio
- **WHEN** la solicitud pasa a `failed`
- **THEN** el widget muestra el error, cierra la ventana del servicio y notifica `failed` al anfitrión

#### Scenario: Servicio no disponible
- **WHEN** `prepare` responde `503`
- **THEN** se muestra que el servicio remoto no está disponible y se puede reintentar, elegir otro método o cancelar

#### Scenario: Recarga con la firma remota en curso
- **WHEN** se abre el widget con una solicitud `firmar` en `signing`
- **THEN** se muestra la espera sin enlace y se sigue consultando el estado

#### Scenario: Sondeo acotado
- **WHEN** se sale de la pantalla de espera
- **THEN** se deja de consultar el estado

#### Scenario: Ventana emergente bloqueada
- **WHEN** el navegador no permite abrir la ventana emergente
- **THEN** el enlace abre el servicio en una pestaña y la espera continúa igual

### Requirement: Métodos como tarjetas con validez
El widget SHALL mostrar los métodos de firma como tarjetas con título, descripción y una etiqueta de validez: «FIRMA DIGITAL» para `token`, «FIRMAR» para la firma remota y «DEMOSTRACIÓN» para la propia, aclarando en esta última que es firma electrónica sin la presunción legal de la firma digital. Las tarjetas SHALL poder elegirse con el teclado.

#### Scenario: Etiquetas
- **WHEN** se muestra la elección con los tres métodos
- **THEN** cada tarjeta lleva su etiqueta y la de demostración aclara que no tiene presunción legal

### Requirement: Token preseleccionado con estado del agente
Cuando `token` esté entre los métodos permitidos, el widget SHALL consultar al agente local y, si responde, preseleccionar el token y mostrar «Firmadoc Agent conectado · token detectado». Si el agente no responde, SHALL mostrar que no se detectó el agente sin impedir elegir otro método.

#### Scenario: Agente conectado
- **WHEN** el agente responde con un token presente
- **THEN** la tarjeta del token queda preseleccionada con el indicador de conexión

#### Scenario: Agente ausente
- **WHEN** el agente no responde
- **THEN** la tarjeta indica que no se detectó el agente y el resto de los métodos siguen disponibles

### Requirement: Tarjeta del documento
El widget SHALL mostrar el documento a firmar con su nombre, páginas, tamaño y estado «Pendiente de firma» con su vencimiento cuando exista. El contexto del widget SHALL incluir `signing_status`, `signature_deadline`, `page_count` y `size_bytes` del documento vigente, sin el binario.

#### Scenario: Documento con vencimiento
- **WHEN** el documento está pendiente de firma con fecha límite
- **THEN** la tarjeta muestra «Pendiente de firma» y «Vence dd/mm/aaaa»

#### Scenario: Sin vencimiento
- **WHEN** el documento no tiene fecha límite
- **THEN** la tarjeta muestra el estado sin vencimiento

#### Scenario: Contexto sin binarios
- **WHEN** se pide el contexto del widget
- **THEN** incluye `signing_status`, `signature_deadline`, `page_count` y `size_bytes` y ningún PDF

### Requirement: Certificados con vigencia
La lista de certificados SHALL mostrar el emisor y la vigencia de cada uno y deshabilitar los vencidos indicando «Venció el dd/mm/aaaa». La elección de un certificado rechazado por el servidor SHALL mostrar el motivo antes de pedir el PIN.

#### Scenario: Certificado vencido
- **WHEN** el token tiene un certificado vencido
- **THEN** aparece deshabilitado con su fecha de vencimiento y no puede elegirse
