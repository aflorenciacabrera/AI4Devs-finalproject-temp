## Context

El flujo de una solicitud (`create` / `prepare` / `complete`) ya es correcto y está probado. El lote debe agregar la agrupación sin duplicar ni debilitar esa lógica: desafíos de un solo uso, versionado inmutable, validación del certificado y webhooks.

## Goals / Non-Goals

**Goals:** firmar N documentos con una confirmación y un PIN; fallos parciales explícitos; ningún cambio en el mecanismo por documento.

**Non-Goals:** widget de lotes, proveedor `firmar`, reintento parcial (ver proposal).

## Decisions

1. **El lote orquesta, la solicitud ejecuta.** `prepare` y `complete` del lote llaman a las funciones existentes de `signature_flow` para cada solicitud. Así toda garantía existente (consumo atómico del desafío, revalidación del certificado, versión inmutable, webhook) vale por documento sin reimplementarla. Alternativa descartada: una ruta de firma especial para lotes (duplicaría la parte más delicada del sistema).
2. **Creación atómica.** `create_request` gana el parámetro `commit` (por defecto `True`, sin cambio para los usos actuales); el lote crea todas las solicitudes con `commit=False` y confirma al final. Si algo falla se hace `rollback` y no queda ninguna fila. Los binarios ya guardados en el almacenamiento quedan huérfanos, como ya ocurre ante una transacción fallida (la referencia incluye el id de la versión, no hay colisiones).
3. **`prepare`: el certificado es común.** Si se rechaza, se rechaza para el primer documento y el error se devuelve sin preparar el resto. Si en cambio un PDF no se puede preparar, el error se devuelve y las solicitudes ya preparadas quedan en `signing` con su desafío (vence solo); volver a llamar a `prepare` es válido y genera desafíos nuevos.
4. **`complete` tolera fallos parciales.** Cada solicitud se completa por separado y su error (código y detalle) se informa en la respuesta con `200`; solo se devuelve error HTTP si el lote no existe, no está preparado o la entrada es inválida. Un documento con firma inválida queda `failed`; uno sin firma recibida (proveedor `token`) queda sin cambios (`signing`); nunca se completa con datos supuestos.
5. **Estado derivado.** El estado del lote se calcula de los estados de sus solicitudes tras cada operación y se guarda en `signature_batch.status` (y `completed_at` al terminar). Una función pura lo calcula, fácil de probar.
6. **Un solo `session_ref`** para todo el lote: el de `X-Session-Ref` o `batch:<id>`. Se usa para todos los desafíos (el desafío sigue atado a su sesión).
7. **Límite de tamaño** configurable (50): acota el trabajo por pedido y el tamaño de la respuesta.
8. **Respuestas sin PDF en `complete`**: para no devolver decenas de megabytes, el resultado por documento incluye `download_url` y la versión, sin `signed_document_base64`.

## Risks / Trade-offs

- Un lote grande se completa en una sola petición y puede tardar (pyHanko firma e incrusta por documento). Se acota con el límite de tamaño; si hiciera falta, el paso siguiente es procesar en segundo plano.
- `prepare` parcial deja desafíos sin usar: vencen solos y no son reutilizables por otra sesión.
