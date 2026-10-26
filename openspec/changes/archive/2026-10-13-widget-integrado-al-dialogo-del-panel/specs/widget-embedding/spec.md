## MODIFIED Requirements

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
