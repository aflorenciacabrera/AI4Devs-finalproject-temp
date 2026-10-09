## 1. Listado de documentos en el servidor (FIRDOC-36)

- [x] 1.1 `list_requests`: agregar `origin` y `document.signature_deadline`, `LEFT JOIN` al lote y orden por grupo (fecha del lote o de la solicitud, `batch_id`, fecha propia)
- [x] 1.2 Agregar los filtros `origin` y `q` (documento por nombre o id externo, o firmante, con comodines escapados) a la ruta y al servicio
- [x] 1.3 Tests: filas de un lote contiguas con una individual intercalada, `origin=batch|individual`, `q` por documento y por firmante con comodines hostiles, vencimiento presente, compatibilidad del filtro `signer`

## 2. Custodia como historia (FIRDOC-37)

- [x] 2.1 `custody()`: construir `timeline` con títulos en español y actores a partir de eventos y entregas de webhook, sin hashes a firmar, cuerpos ni secretos; tipos desconocidos con su nombre técnico
- [x] 2.2 Agregar `technical` (transacción, proveedor, nivel, certificado, emisor, serie, firmante, hash original y firmado) sin IP de origen
- [x] 2.3 `GET /api/v1/admin/documents/{id}/versions/{n}/download` desde el almacén, con `no-store`, `404` y autenticación de administración
- [x] 2.4 Tests: historia completa de una firma con token (orden y actores), rechazo de certificado, firma fallida, webhook fallido, ausencia de datos sensibles, descarga de v1 sin firma y de v2 firmada, `404`/`401`

## 3. Integradores en el servidor (FIRDOC-38)

- [x] 3.1 Migración `0008`: `integrating_system.disabled_at` (nullable, aditiva, downgrade compatible con SQLite) y campo en el modelo
- [x] 3.2 `current_system`: rechazar con el mismo `401` a un integrador deshabilitado
- [x] 3.3 `services/integrator_admin.py`: listar, crear, cambiar orígenes, rotar secreto de webhook, rotar API key, deshabilitar y habilitar, protegiendo el sistema interno (`409`) y registrando cada acción en `admin_event` sin secretos
- [x] 3.4 Rutas `/api/v1/admin/integrators` con esquemas; secretos en claro solo al crear y rotar, nunca el hash
- [x] 3.5 Tests: alta con credenciales de una sola vez, listado sin secretos ni hash, validaciones (duplicado, reservado, origen inválido), la API key rotada invalida la anterior, deshabilitar y habilitar, el sistema interno protegido, eventos sin secretos, migración reversible

## 4. Navegación y estilo del panel (FIRDOC-36)

- [x] 4.1 Reemplazar las pestañas por la barra lateral con las cinco secciones y agrupar webhooks y eventos en «Auditoría», anclas y certificado en «Confianza», conservando `LOADERS`, CSP y tema claro/oscuro
- [x] 4.2 Estilos del mockup (barra lateral, tablas, estados con color) y adaptación a pantallas angostas; foco y estado activo accesibles
- [x] 4.3 Actualizar las pruebas en Chrome real del panel a la nueva navegación

## 5. Listado y detalle en la interfaz (FIRDOC-36, 37)

- [x] 5.1 «Documentos»: tabla con Documento (`vN`), Firmante, Fecha, Proveedor, Origen, Estado con color y vencimiento, búsqueda y filtros (estado, proveedor, origen, fechas) y paginación; todo con `textContent`
- [x] 5.2 Detalle: «Volver a Documentos», encabezado con estado y descarga del firmado, línea de tiempo, tarjeta Versiones con descarga y Detalle técnico
- [x] 5.3 Descarga de versiones con el token en `Authorization` (no en la URL) y guardado como archivo
- [x] 5.4 Pruebas en Chrome real: origen individual y de lote, vencimiento, filtros y búsqueda, texto hostil, detalle con línea de tiempo y descarga de v1

## 6. Integradores en la interfaz (FIRDOC-38)

- [x] 6.1 Pantalla «Integradores»: listado, formulario de alta, edición de orígenes, rotaciones con confirmación, deshabilitar/habilitar y sistema interno sin acciones
- [x] 6.2 Cuadro de credenciales de un solo uso (API key y secreto, «Copiar», aviso) que no persiste nada en el navegador
- [x] 6.3 Pruebas en Chrome real: alta con credenciales visibles una vez, rotar con confirmación cancelada y aceptada, deshabilitar, nada en `sessionStorage`/`localStorage`

## 7. Documentación y cierre

- [x] 7.1 Actualizar `docs/admin.md` (navegación, columnas, línea de tiempo, descarga de versiones, integradores, límite de la IP de origen)
- [x] 7.2 Suite completa de backend y e2e, linter; corregir regresiones
- [x] 7.3 Pasar FIRDOC-36, 37 y 38 a Listo en Jira al cerrar el change
