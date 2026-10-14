## MODIFIED Requirements

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
