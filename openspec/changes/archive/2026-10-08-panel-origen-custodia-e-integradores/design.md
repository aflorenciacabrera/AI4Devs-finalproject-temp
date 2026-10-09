## Context

- El panel (`admin_ui/`) es HTML/JS/CSS propios sin dependencias, con CSP estricta; usa pestañas (`data-tab`), un `api()` con Bearer y construye todo con `textContent`. El listado y la custodia salen de `services/admin.py` (`list_requests`, `custody`).
- `list_requests` ya devuelve `batch_id` en la custodia pero no en el listado; el documento tiene `signature_deadline`. Los eventos de auditoría de una solicitud son `created`, `provider_selected`, `prepared`, `rejected`, `signed`, `failed`, `timestamp_unavailable` (y `batch_*` por lote); las entregas de webhook son una tabla aparte.
- Los integradores se administran solo por la CLI (`integrators.py`: crear, rotar secreto, listar); `IntegratingSystem` no tiene estado ni marca de deshabilitado. El sistema interno del panel («Firmadoc (panel)») se creó en FIRDOC-44.
- El backend no registra la IP de origen.

## Goals / Non-Goals

**Goals:** acercar el panel al mockup (navegación, listado, detalle) y cerrar la brecha de gestión de integradores, sin dependencias nuevas y sin aflojar la seguridad.

**Non-Goals:** roles de administrador, eliminar integradores, registrar IP, nuevas pantallas del mockup (FIRDOC-39), README.

## Decisions

1. **La línea de tiempo se arma en el servidor** (`custody()` agrega `timeline`) y la interfaz solo la dibuja. Evita duplicar la lógica de títulos y actores en JavaScript, permite probarla con pytest y mantiene los datos crudos (`events`, `challenges`, `webhook_deliveries`) para quien los use. Un diccionario `EVENT_TITLES` por tipo de evento; los tipos desconocidos se muestran con su nombre técnico en vez de perderse.
2. **Origen del listado**: se agrega `origin` al ítem y `ORDER BY` por «fecha de agrupación» (`COALESCE(batch.created_at, request.created_at)` desc, luego `batch_id`, luego la fecha de la solicitud) con un `LEFT JOIN` a `signature_batch`. Así las filas de un lote quedan juntas aunque sus `created_at` difieran en milisegundos. La etiqueta «Lote #xxxxxxxx» usa los primeros 8 caracteres del id (el lote no tiene número secuencial y no se agrega uno).
3. **Búsqueda `q`** junto a los filtros existentes: coincide con el `external_document_id` (escapando comodines, como el filtro de firmante) o con el firmante. El filtro `signer` actual se conserva por compatibilidad.
4. **Descarga de versiones por administración**: `GET /api/v1/admin/documents/{id}/versions/{n}/download` lee del almacén configurado igual que la descarga de integradores, sin pasar por la API key. Es solo lectura y queda sin evento (las lecturas no se auditan, como el resto del panel).
5. **Integrador deshabilitado = columna `integrating_system.disabled_at` (migración `0008`, nullable, aditiva)**. `current_system` (API key) rechaza con el mismo `401` que una clave inválida para no revelar la causa. El widget no cambia: sus tokens son por solicitud y vencen, de modo que una firma en curso termina. Alternativa descartada: borrar el integrador (rompe la trazabilidad de documentos y auditoría).
6. **Servicio `services/integrator_admin.py`** reutiliza `integrators.create`, `new_api_key` y `new_webhook_secret`; cada función registra el `AdminEvent` con `admin.record` en la misma transacción. Los secretos en claro solo salen en la respuesta de crear y rotar; el listado nunca expone `api_key_hash`.
7. **Protección del sistema interno** por nombre reservado (`RESERVED_NAMES`): crear con ese nombre ya se rechaza; modificar, rotar o deshabilitar devuelve `409`.
8. **Navegación lateral**: se reemplaza `nav` por una barra lateral (`<nav>` con botones) que mantiene los `data-tab` y los `LOADERS` actuales; «Documentos» = solicitudes (+ detalle), «Auditoría» = webhooks + eventos, «Confianza» = anclas + certificado propio. En pantallas angostas la barra pasa arriba. La caja «Custodia por ID» deja de ser una pestaña: al detalle se llega desde el listado.
9. **Detalle técnico** toma la última solicitud firmada de la custodia: proveedor, nivel de la versión que creó, certificado (sujeto, emisor, serie), hash de la v1 y de la versión vigente. Sin IP de origen (no existe el dato).
10. **Credenciales de un solo uso en el navegador**: se muestran en un cuadro propio con «Copiar» y se descartan al cerrarlo; nunca van a `sessionStorage`, `localStorage` ni a la URL, y no se vuelven a pedir al servidor.

## Risks / Trade-offs

- [Cambiar la navegación rompe pruebas existentes del panel] → las pruebas en Chrome real (`test_admin_e2e`, `test_panel_sign_e2e`) se actualizan a los nuevos selectores y siguen siendo la red de seguridad.
- [Deshabilitar un integrador con firmas en curso] → los enlaces del widget ya emitidos terminan; se documenta.
- [Rotar la API key deja caído al integrador hasta que la actualice] → confirmación explícita en la interfaz y aviso del efecto.
- [Reordenar el listado por grupos cambia el orden estricto por fecha] → se documenta; dentro de cada grupo se mantiene el orden por fecha.
- [Lote sin número secuencial] → la etiqueta usa el prefijo del id; suficiente para ubicarlo, sin migrar.

## Open Questions

- Ninguna que cambie el alcance. La decisión sobre «IP de origen» queda tomada (se omite y se anota para el mockup).
