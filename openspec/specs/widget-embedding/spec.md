# Widget Embedding Specification

## Purpose

Integración del widget en la página anfitriona: iframe, Web Component, mensajes postMessage con destinatarios explícitos, página de ejemplo, guía Angular y prueba en un navegador real.

## Requirements

### Requirement: Embebido por iframe
El widget SHALL poder embeberse con un `<iframe src="{signing_url}">` desde cualquier origen listado en los `allowed_origins` del integrador, sin que el widget dependa del framework de la página anfitriona, y SHALL negarse a mostrarse dentro de cualquier otro origen. El aislamiento (`sandbox`) que aplican el Web Component, la página de ejemplo y los paneles de Firmadoc, y el que documenta la guía de integración, SHALL permitir que el widget abra una pestaña nueva fuera del aislamiento (el enlace «Continuar en el servicio de firma» de la firma remota) y descargue archivos, además de ejecutar scripts y usar su propio origen.

#### Scenario: Origen permitido
- **WHEN** una página de un origen permitido embebe `signing_url`
- **THEN** el widget se carga y funciona dentro del iframe sin recargar la página anfitriona

#### Scenario: Origen no permitido
- **WHEN** una página de otro origen intenta embeber el mismo enlace
- **THEN** el navegador bloquea el marco por la política `frame-ancestors` y el widget no se muestra

#### Scenario: Enlace al servicio de firma remota
- **WHEN** la persona elige la firma remota dentro del widget embebido con el aislamiento recomendado y pulsa «Continuar en el servicio de firma»
- **THEN** la página de autorización del servicio se abre en una pestaña nueva, sin aislamiento, y permite enviar su formulario

### Requirement: Mensajes hacia la página anfitriona
El widget SHALL notificar a la página que lo embebe (`window.parent`) o, si corre en una ventana propia, a la que lo abrió (`window.opener`) con `postMessage`, dirigiendo cada mensaje **explícitamente** a cada origen de `allowed_origins` (nunca `"*"`), con la forma `{source: "firmadoc", type, requestId, ...}` y los tipos `firmadoc:ready`, `firmadoc:signed`, `firmadoc:failed`, `firmadoc:cancelled` y `firmadoc:closed`.

#### Scenario: Firma completada
- **WHEN** la firma se completa
- **THEN** la página anfitriona recibe `firmadoc:signed` con `requestId` y el bloque `document` (identificador, número de versión, `is_active_version`, `signing_status`, `signature_level`), sin el PDF ni el token

#### Scenario: Listo
- **WHEN** el widget termina de cargar el contexto
- **THEN** la página anfitriona recibe `firmadoc:ready`

#### Scenario: Falla
- **WHEN** la firma termina en un error irrecuperable
- **THEN** la página anfitriona recibe `firmadoc:failed` con un `code` y sin detalles internos

#### Scenario: Cierre
- **WHEN** la persona pulsa "Cerrar" o "Cancelar"
- **THEN** la página anfitriona recibe `firmadoc:closed` o `firmadoc:cancelled` respectivamente

#### Scenario: Destinatario equivocado
- **WHEN** la página que embebe o abre el widget no pertenece a ningún origen de `allowed_origins`
- **THEN** ningún mensaje se entrega a esa página

### Requirement: Sin mensajes entrantes
El widget SHALL NOT aceptar mensajes de la página anfitriona ni de ninguna otra ventana para cambiar su comportamiento.

#### Scenario: Mensaje entrante
- **WHEN** la página anfitriona envía un mensaje al iframe
- **THEN** el widget lo ignora

### Requirement: Web Component
El proyecto SHALL ofrecer `/widget.js`, que registra el elemento `<firmadoc-widget signing-url="...">`; el elemento crea el iframe, aplica un tamaño por defecto, y reemite los mensajes del widget como eventos DOM (`firmadoc-signed`, `firmadoc-failed`, `firmadoc-cancelled`, `firmadoc-closed`, `firmadoc-ready`) solo si provienen de la ventana de su propio iframe y del origen de la `signing-url`.

#### Scenario: Uso del elemento
- **WHEN** se agrega `<firmadoc-widget signing-url="...">` a una página
- **THEN** se crea un iframe con esa URL y se emiten los eventos del widget

#### Scenario: Mensaje de otro origen
- **WHEN** llega un mensaje desde una ventana o un origen distintos
- **THEN** el elemento no emite ningún evento

#### Scenario: Cambio de URL
- **WHEN** cambia el atributo `signing-url`
- **THEN** el iframe se recarga con la nueva URL

### Requirement: Página anfitriona de ejemplo
El proyecto SHALL incluir una página anfitriona de ejemplo que embeba el widget por iframe y por Web Component, lo abra en una ventana emergente (`mode=popup`, desde un botón), y que muestre los mensajes recibidos, usable para probar la integración y como base de la prueba de punta a punta.

#### Scenario: Página de ejemplo
- **WHEN** se abre la página de ejemplo con una `signing_url`
- **THEN** embebe el widget y registra cada mensaje recibido

#### Scenario: Ventana emergente de ejemplo
- **WHEN** se abre la página de ejemplo con `mode=popup` y se pulsa el botón
- **THEN** la `signing_url` se abre en una ventana propia y la página registra los mensajes que recibe de esa ventana y su cierre

### Requirement: Guía de integración con Angular
`widget/README.md` SHALL documentar la integración desde un componente Angular: sanitización de la URL del iframe (`DomSanitizer`), escucha de los mensajes validando el origen del emisor y la ventana del iframe, uso del Web Component con `CUSTOM_ELEMENTS_SCHEMA`, cómo obtener la `signing_url` desde el backend del sistema integrador (nunca desde el navegador), y la alternativa de ventana emergente (apertura en un gesto del usuario y validación de `event.source` contra la ventana abierta).

#### Scenario: Ejemplo Angular
- **WHEN** un desarrollador Angular sigue la guía
- **THEN** dispone de un componente de ejemplo que embebe el widget y reacciona a `firmadoc:signed`

#### Scenario: Alternativa en Angular
- **WHEN** el anfitrión Angular no puede delegar el permiso de red local
- **THEN** la guía le muestra cómo abrir la `signing_url` en una ventana propia y escuchar sus mensajes

### Requirement: Prueba de punta a punta en un navegador real
La suite SHALL incluir una prueba que, en Chrome o en Edge (elegible con `FIRMADOC_E2E_BROWSER`, Chrome por defecto), abra una página anfitriona de un origen permitido, complete la firma con el proveedor `token` contra el servidor y el agente reales (con una PKI de prueba), verifique que la página recibe `firmadoc:signed` y que el PDF descargado tiene una firma válida, y cubra al menos: certificado rechazado antes del PIN, agente no disponible, cancelación y PIN incorrecto con reintento manual, firma `local`, bloqueo del iframe desde un origen no permitido, y la firma en una ventana emergente. La documentación SHALL indicar cómo ejecutarla en ambos navegadores y que Firefox y Safari no están verificados.

#### Scenario: Flujo completo
- **WHEN** se ejecuta la prueba de punta a punta
- **THEN** la firma se completa dentro del iframe y la página anfitriona recibe el mensaje `firmadoc:signed`

#### Scenario: En Edge
- **WHEN** se ejecuta con `FIRMADOC_E2E_BROWSER=msedge`
- **THEN** las mismas pruebas corren en Edge

#### Scenario: Navegador no disponible
- **WHEN** el navegador elegido o los archivos compilados del widget no están disponibles
- **THEN** la prueba se omite indicando el motivo

### Requirement: Embebido por el propio servidor
La página de firma SHALL poder embeberse desde el origen del propio servidor cuando la solicitud pertenece al sistema integrador interno del panel, porque su `frame-ancestors` se calcula con los orígenes permitidos del sistema (el origen de `public_base_url`). Para cualquier otro sistema SHALL mantenerse la regla vigente de usar solo sus orígenes permitidos.

#### Scenario: Solicitud del panel
- **WHEN** se pide `/sign/{id}` de una solicitud creada desde el panel
- **THEN** `frame-ancestors` contiene el origen del servidor y el panel puede embeberla

#### Scenario: Solicitud de otro integrador
- **WHEN** se pide `/sign/{id}` de una solicitud de un integrador externo
- **THEN** `frame-ancestors` contiene solo los orígenes de ese integrador; el panel no puede embeberla

### Requirement: Ventana emergente como modo alternativo
Además del iframe (modo principal y el que usan los paneles de Firmadoc), la `signing_url` SHALL poder abrirse en una ventana propia con `window.open` desde una página de un origen de `allowed_origins`. En ese modo el widget SHALL avisar a la ventana que lo abrió (`window.opener`) con los mismos mensajes y la misma regla de destinatario explícito por origen permitido, SHALL cerrar su ventana al pulsar «Cerrar» después de avisar, y SHALL funcionar sin delegación del permiso de red local (lo pide su propio origen). Sin ventana anfitriona (pestaña abierta a mano o `opener` ausente o cerrado) SHALL NOT enviar mensajes ni cerrar nada. Las guías SHALL documentar este modo como alternativa al iframe, con sus costos (gesto del usuario para evitar el bloqueo de ventanas emergentes, salida de la aplicación, y que la dirección de la firma queda visible en la barra del navegador aunque el token se borre de ella antes de dibujar) y cuándo conviene (anfitriones que eliminan el atributo `allow` o no pueden delegar el permiso).

#### Scenario: Firma en ventana propia
- **WHEN** una página de un origen permitido abre la `signing_url` con `window.open` y la persona firma
- **THEN** la página que la abrió recibe `firmadoc:ready` y `firmadoc:signed`, sin el token ni el PDF

#### Scenario: Cierre de la ventana
- **WHEN** la persona pulsa «Cerrar» en la ventana propia
- **THEN** la página que la abrió recibe `firmadoc:closed` y la ventana se cierra

#### Scenario: Sin anfitrión
- **WHEN** la `signing_url` se abre a mano en una pestaña
- **THEN** el widget funciona, no envía ningún mensaje y «Cerrar» no cierra la pestaña

#### Scenario: Anfitrión de otro origen
- **WHEN** una página de un origen no permitido abre la ventana
- **THEN** no recibe ningún mensaje
