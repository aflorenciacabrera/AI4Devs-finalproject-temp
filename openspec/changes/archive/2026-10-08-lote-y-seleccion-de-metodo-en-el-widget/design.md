## Context

- El widget (`widget/`) es React con una máquina de estados pura (`state/machine.ts`), un hook (`useSigningFlow.ts`), clientes del servidor y del agente (`api/`) y pantallas por estado. Todo está pensado alrededor de **una solicitud**: la URL es `/sign/{uuid}`, el token se valida contra ese id y el contexto es un `WidgetContext` de un documento.
- El servidor ya tiene el lote completo (`services/signature_batch.py`: crear, preparar, completar, estado por documento con errores en la respuesta de `complete`), pero solo detrás de la API key del integrador.
- `signing_token` firma `{rid, exp}` y se verifica contra el id de la ruta; un token de otro id no sirve. El agente (`agent/`) ya firma N hashes con un PIN y su diálogo ya muestra la cantidad de documentos.
- `batch.provider` es único por lote; `signature_batch` no tiene métodos permitidos. `flow.prepare` con `firmar` abre una operación remota por documento: no hay soporte por lote.
- El panel ya embebe el widget de una solicitud (FIRDOC-44/45) y acepta un solo PDF.

## Goals / Non-Goals

**Goals:**
- Firmar un lote desde el widget con un certificado y un PIN, ver el resultado parcial, descargar los firmados y reintentar los fallidos.
- Elegir método con tarjetas de validez, mostrar el documento y su estado, y el estado del agente, según el mockup.
- Reutilizar al máximo: token, página, pantallas de certificado/PIN, casos de uso de lote.

**Non-Goals:**
- Firma remota en lote, persistir errores por documento, reintentos dentro del mismo lote (ver «Fuera de alcance» de la propuesta).

## Decisions

1. **El token de lote reutiliza `signing_token` con el id del lote como `rid`.** Los UUID no colisionan entre tablas y cada ruta verifica contra su propio id, así que un token de lote no abre solicitudes ni al revés (se prueba). Sin cambios de formato ni de secreto.
2. **Ruta de página `/sign/batch/{id}` y rutas del widget `/api/v1/widget/batches/{id}`**, en módulos separados (`widget_batch_routes.py`) con su propia dependencia `batch_auth`. Se prefiere duplicar la dependencia de autenticación (corta) a generalizar `widget_auth` y arriesgar el flujo individual.
3. **El widget decide el modo por la ruta y reutiliza la máquina de estados mediante un adaptador.** `requestIdFromPath` pasa a devolver `{kind: "request" | "batch", id}`. Para un lote se crea un cliente del servidor con la misma interfaz (`getContext`, `selectProvider`, `prepare`, `complete`, `downloadPdf`) que convierte el lote en un `WidgetContext` con un bloque opcional `batch` (lista de documentos y resultado); los estados terminales del lote (`completed`, `partial_failure`, `failed`) se mapean a `signed` para que la máquina llegue a `success`, donde la pantalla decide mostrar el resultado del lote. Así la máquina, el hook, y las pantallas de certificado, validación y PIN se reutilizan sin duplicar (la elección de método y la confirmación local muestran además la lista de documentos). Alternativa del diseño original (máquina y hook propios): descartada al ver que duplicaba ~500 líneas y todas las pruebas de la firma individual dejaban de cubrir el flujo del lote.

4. **Un `prepare` y un `complete` por lote**, no por documento. `prepare` devuelve N desafíos; el hook los envía en una sola llamada al agente (un PIN) y luego un único `complete` con las N firmas. Si el agente firma solo algunos, los demás quedan en `signing` (comportamiento ya definido por el servidor).
5. **Métodos del lote: columna `signature_batch.allowed_providers` (migración `0007`, nullable, aditiva)**, validada como en las solicitudes y copiada a cada solicitud. Se excluye `firmar` en la validación de creación del lote (`422`) en vez de dejar que falle al preparar. Al elegir método en el widget se actualizan el lote y todas sus solicitudes pendientes en una transacción.
6. **Contexto del lote sin binarios**: páginas y tamaño por documento se calculan al pedir el contexto leyendo la versión vigente del almacén; para lotes de hasta 50 documentos es lineal y aceptable (cacheable más adelante). Mismo cálculo para `page_count`/`size_bytes` del contexto individual (FIRDOC-35), implementado una vez en un helper compartido con la carga del panel.
7. **Descarga de los firmados como ZIP armado en el servidor** (`zipfile`, `ZIP_STORED`, archivo temporal en disco para no retener hasta ~1 GB en memoria), en vez de N descargas encadenadas que los navegadores bloquean. El nombre de cada PDF dentro del ZIP se saniza y se desambigua.
8. **Reintento = otro lote**: `POST /retry` crea un lote nuevo con los `document_id` de los solicitados `failed`, mismo sistema, firmante y métodos, y devuelve `signing_url`; el widget navega al nuevo lote reemplazando el estado (sin recargar la página ni exponer el token anterior). Los firmados no se vuelven a firmar porque no entran al nuevo lote.
9. **Errores por documento solo en la respuesta de `complete`**: el estado queda en el hook; al recargar, el ítem figura `failed` con mensaje genérico. Evita una tabla nueva; se documenta como límite.
10. **Mensaje al anfitrión `firmadoc:batch-completed`** con la forma de `publicDocument` extendida a un arreglo; sin PDF, firmas ni token. El panel lo consume validando origen y ventana, como en FIRDOC-45.
11. **Tarjetas de método (FIRDOC-35)**: se reescribe `ChooseProvider` como grupo de tarjetas con `role="radiogroup"` (accesible por teclado) usado por la firma individual y por el lote. El estado del agente se consulta con el cliente existente antes de renderizar; mientras responde, el token figura «Buscando Firmadoc Agent…». Si el agente responde, token queda preseleccionado.
12. **Panel**: `POST /api/v1/admin/signing-batch-uploads` hermano del individual (decisión 3 de FIRDOC-44), mismo servicio interno con una función `upload_batch` que valida todo antes de insertar (atomicidad), y la sección del panel pasa a un arreglo de archivos (`FileList`) con listado y «Quitar» por archivo.

## Risks / Trade-offs

- [ZIP grande en el servidor] → archivo temporal y `ZIP_STORED`; el límite real es `max_batch_size × max_document_bytes`. Si preocupa, bajar `FIRMADOC_MAX_BATCH_SIZE`.
- [Duplicar autenticación de widget para lotes] → duplicación acotada y probada (token cruzado) a cambio de no tocar el flujo individual.
- [Páginas/tamaño leyendo cada PDF] → costo lineal por pedido de contexto; aceptable hoy, medir si crece.
- [Reintento crea documentos nuevos en el historial del lote] → trazabilidad completa (cada lote queda auditado); el costo es que el lote original queda `partial_failure`.
- [Firma remota ausente del lote] → la tarjeta se muestra deshabilitada con el motivo, para no divergir del mockup sin explicar.
- [Cambio de la pantalla de elección toca el flujo individual] → las pruebas existentes de `widget/tests` (choice, flow) son la red de seguridad y se adaptan solo en textos/selectores.

## Open Questions

- Ninguna que cambie el alcance. Si el agente no soporta N desafíos por una limitación no vista en `agent-contract.md`, la tarea 6.2 lo detecta con SoftHSM antes de seguir y se pausa para ajustar el contrato.
