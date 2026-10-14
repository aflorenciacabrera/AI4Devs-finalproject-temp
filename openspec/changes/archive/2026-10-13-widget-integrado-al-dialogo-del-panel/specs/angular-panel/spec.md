## REMOVED Requirements

### Requirement: Carga de documentos y widget embebido en Angular
**Reason**: la ventana propia del panel (FIRDOC-57) se descarta porque deja visible la dirección de la firma; el requisito se reemplaza por «Carga de documentos y widget en el diálogo de Angular», que vuelve al diálogo con el iframe y suma el tema del panel.
**Migration**: ninguna para integradores; el panel abre el diálogo como antes de FIRDOC-57.

#### Scenario: Un PDF
- **WHEN** elige un PDF válido y pulsa «Cargar y firmar»
- **THEN** se muestra la tarjeta del documento y el widget se abre en una ventana propia con la `signing_url`

## ADDED Requirements

### Requirement: Carga de documentos y widget en el diálogo de Angular
La sección «Firmar documento» SHALL usar el componente de carga de PrimeNG para elegir o arrastrar uno o varios PDF, rechazar en el navegador los archivos que no sean PDF o superen el tamaño máximo (sin enviar nada), listar los archivos elegidos con «Quitar» por archivo y ofrecer «Cargar y firmar» (con la cantidad cuando hay varios). Al confirmar SHALL enviar un archivo a `POST /api/v1/admin/signing-uploads` o varios a `POST /api/v1/admin/signing-batch-uploads`, mostrar la tarjeta del documento (nombre, páginas, tamaño) o la lista del lote, el aviso de versiones y el widget en un diálogo con un `iframe` con la `signing_url` devuelta más `?theme=<tema del panel>` antes del fragmento (para que el widget use los mismos colores), con `sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-popups-to-escape-sandbox"`, `allow="local-network-access; local-network; loopback-network"` y `referrerpolicy="no-referrer"`. SHALL NOT abrir el widget en una ventana propia (la dirección quedaría visible en el navegador). SHALL aceptar los mensajes del widget solo si vienen de la ventana del iframe y del origen de la `signing_url`, mostrar el resultado (firmado, lote «N de M», fallido, cancelado) y, si el diálogo se cierra sin firmar, avisarlo. «Quitar» y «Reemplazar» SHALL volver a la carga sin widget.

#### Scenario: Un PDF
- **WHEN** elige un PDF válido y pulsa «Cargar y firmar»
- **THEN** se muestra la tarjeta del documento y el diálogo con el widget y la `signing_url` (con el tema del panel)

#### Scenario: Varios PDF
- **WHEN** elige tres PDF válidos y confirma
- **THEN** se envían como lote y se muestra la lista de los tres y el widget de lote

#### Scenario: Archivo inválido
- **WHEN** entre los archivos hay uno que no es PDF
- **THEN** se indica cuál es y no se envía nada

#### Scenario: Mensaje de otra ventana u origen
- **WHEN** llega un `message` que no proviene de la ventana del iframe o de su origen
- **THEN** se ignora

#### Scenario: Diálogo cerrado sin firmar
- **WHEN** la persona cierra el diálogo sin haber firmado
- **THEN** la tarjeta avisa que el documento quedó sin firmar y permite abrir el módulo de nuevo
