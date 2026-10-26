## Why

El servidor ya firma en lote (FIRDOC-22: `/signature-batches`, un desafío por documento, estado `partial_failure`) y el agente ya firma N hashes con un solo PIN, pero **el widget no tiene ninguna pantalla ni credencial de lote**: una persona no puede firmar varios documentos juntos desde el navegador. Además, la elección de método del widget es hoy una lista de botones sin contexto, distinta del mockup (`Main`, `MainBatch`): no muestra el documento ni su estado, ni la validez de cada método, ni si el token está conectado.

Implementa **FIRDOC-34** (widget: firma en lote con un solo PIN y resultado parcial; pantallas `MainBatch`, `AgentDialogBatch`, `BatchSuccess`) y **FIRDOC-35** (widget: selección de método y tarjeta de documento según el mockup `Main`), dentro de la épica de widget (FIRDOC-3) y completando la carga de varios PDF de la sección «Firmar documento» de FIRDOC-33/45. Corresponde a las HU del README de firma en lote y de elección de proveedor.

## What Changes

- **Credencial y página de lote**: el token del widget (ya acotado a un id) se emite también para un lote; nueva página `/sign/batch/{id}` que sirve el mismo widget y la URL `signing_url` de lote.
- **Endpoints del widget para lotes** (`/api/v1/widget/batches/{id}`): contexto, elección de método, preparar, completar, descarga de los firmados (ZIP) y reintento de los fallidos (crea otro lote solo con ellos).
- **Lotes con método elegible**: `signature_batch.allowed_providers` (migración aditiva) y `allowed_providers` opcional al crear el lote; `signing_url` en la respuesta de creación. Solo `token` y `local` en lotes.
- **Widget (FIRDOC-34)**: pantalla de revisión del lote (lista con nombre, páginas y tamaño, «Firmar N documentos»), certificado elegido y validado **una sola vez**, PIN **una sola vez**, pantalla de resultado «N de M documentos firmados» con estado por documento, «Descargar firmados» y «Reintentar» por documento fallido, y mensaje `postMessage` al anfitrión con el resultado del lote (sin PDF ni token).
- **Widget (FIRDOC-35)**: métodos como tarjetas con etiqueta de validez («FIRMA DIGITAL», «FIRMAR», «DEMOSTRACIÓN»), token preseleccionado con el indicador «Firmadoc Agent conectado · token detectado», tarjeta del documento con nombre, páginas, tamaño y estado «Pendiente de firma» con su vencimiento, y revisión de las pantallas de certificado, rechazo, espera de PIN y éxito contra el mockup.
- **Contexto del widget**: `WidgetContext` agrega `signing_status`, `signature_deadline`, páginas y tamaño del documento.
- **Panel (continuación de FIRDOC-45)**: la sección «Firmar documento» acepta varios PDF; con más de uno crea un lote con `POST /api/v1/admin/signing-batch-uploads` y embebe el widget de lote.

## Capabilities

### New Capabilities
- `widget-batch-signing`: credencial, página, endpoints y pantallas del widget para firmar un lote con un solo certificado y un solo PIN, con resultado parcial, descarga y reintento.

### Modified Capabilities
- `signature-batches`: método elegible por lote y `signing_url` al crearlo.
- `widget-provider-choice`: tarjetas de método con validez, indicador del agente, tarjeta del documento y campos nuevos en el contexto del widget.
- `pdf-upload-signing`: carga de varios PDF desde el panel que crea un lote.
- `admin-panel`: la sección «Firmar documento» acepta varios archivos.

## Impact

- Código backend: `signing_token` (sin cambios de formato), `api/pages.py`, `api/widget_routes.py` (+ módulo de rutas de lote), `services/widget.py`, `services/signature_batch.py`, `services/panel_upload.py`, `api/admin_routes.py`, `api/schemas.py`, `models.py`, nueva migración `0007`.
- Código widget: `bootstrap/token.ts`, `main.tsx`, `App.tsx`, `api/` (tipos y cliente), `state/` (máquina y hook de lote), `screens/` (revisión, resultado, tarjetas de método), `messages/es.ts`, estilos, `embed/hostMessages.ts`; y `admin_ui` del panel.
- API: endpoints nuevos bajo `/api/v1/widget/batches` y `/api/v1/admin`; campos nuevos opcionales (compatibles) en la creación de lotes y en el contexto del widget. Migración aditiva, no destructiva.
- Docs: `docs/signature-batches.md`, `docs/admin.md` y la guía del widget.
- Dependencias: ninguna nueva.

## Fuera de alcance

- **Firma remota (`firmar`) en lotes**: el servidor no la soporta por lote (abriría una operación remota por documento). La tarjeta se muestra en el widget de lote deshabilitada con el aviso del límite del servicio; implementarla es un cambio aparte.
- Reintento automático o parcial dentro del mismo lote: el reintento crea otro lote con los `document_id` fallidos, como define `docs/signature-batches.md`.
- Persistir el motivo de cada error para verlo tras recargar la página (se muestra el de la respuesta de `complete`; al recargar, el estado `failed` sin detalle).
- El diálogo del agente (`AgentDialogBatch`): ya muestra la cantidad de documentos en `firmadoc_agent/ui_tk.py`; solo se verifica.
- Panel: columnas, custodia y gestión de integradores (FIRDOC-36, 37, 38); README (FIRDOC-40).
