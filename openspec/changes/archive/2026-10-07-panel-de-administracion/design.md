## Context

El servidor ya guarda todo lo necesario para auditar (solicitudes, versiones inmutables, eventos, desafíos, entregas). Faltan una forma segura de leerlo y de operar la confianza (anclas y certificado propio). La autenticación existente es por API key de integrador, que no debe servir para administrar. Las anclas viven en un directorio de archivos cargado una vez por proceso, y el certificado propio en archivos con la clave en disco.

## Goals / Non-Goals

**Goals:** ver y filtrar el historial, reconstruir la custodia, reenviar webhooks, gestionar anclas y rotar el certificado propio, dejando rastro inmutable de todo cambio. Un panel mínimo y seguro.

**Non-Goals:** usuarios/roles/SSO, revocación de firmantes, límites de intentos (ver proposal).

## Decisions

1. **Un token de administración aparte de las API keys**, `FIRMADOC_ADMIN_TOKEN` (≥ 32 caracteres, validado como el secreto del widget). Sin él, toda ruta de administración responde `404` (la funcionalidad "no existe"), no `401`: no revela que hay un panel. La comparación usa `hmac.compare_digest`. Alternativa descartada: reutilizar las API keys de integrador con un indicador de administrador (mezcla dos niveles de privilegio en una credencial que viaja en los sistemas integrados).
2. **Token en `Authorization: Bearer`, guardado en `sessionStorage` por el panel; sin cookies.** Sin cookie no hay CSRF. `sessionStorage` se borra al cerrar la pestaña. La CSP estricta (`script-src 'self'`, sin estilos ni scripts en línea) y construir el DOM con `textContent` (nunca `innerHTML`) cierran la puerta al XSS que robaría el token. `Cache-Control: no-store` y `frame-ancestors 'none'`.
3. **`admin_event` append-only en la base**, con los mismos triggers que `audit_event`, y no un simple log: un cambio de anclas es la acción más sensible del sistema y debe sobrevivir a la rotación de logs. Campos: `actor`, `action`, `detail` (JSON), `created_at`. Solo se registran acciones que **modifican**; las lecturas no, para no inflar la tabla. `actor` es `"admin"` mientras haya un único token (queda el campo listo para usuarios).
4. **Las anclas se gestionan como archivos del directorio de confianza**, el mismo mecanismo que ya usa la validación (un archivo por ancla, nombre derivado de la huella). Agregar valida que sea un certificado X.509, no esté vencido y sea una CA o autofirmado, y escribe el archivo sin sobrescribir; quitar borra el archivo de esa ancla (se rechaza con `409` si el archivo contiene más de un certificado, para no borrar otras sin querer). Tras cada cambio se invalida la caché de `load_trust_store`. Con varias réplicas del servidor, cada una debe ver el mismo directorio (volumen compartido) y se recargan al reiniciar; se anota en la documentación.
5. **Rotación del certificado propio sin invalidar lo firmado**: el certificado público vigente se archiva en `local_cert_dir/archive/` y **la clave privada vieja se destruye** (si hubo compromiso, no debe quedar utilizable); se genera un par nuevo. La verificación de documentos usa como anclas el certificado vigente **y** los archivados, de modo que las firmas ya emitidas siguen verificándose. Límite conocido: tras un compromiso de la clave, una firma antigua no se distingue de una forjada con la clave robada (no hay sello de tiempo de una TSA todavía); se documenta y lo cubre el cambio de sello de tiempo.
6. **Listado con filtros y paginación en la base**, nunca en memoria: filtros por integrador, estado, proveedor, firmante (identificador exacto o nombre que contenga el texto, sin distinguir mayúsculas, con los comodines `%` y `_` escapados), y rango de fechas de creación; `limit` ≤ 200 (50 por defecto) y `offset`; devuelve `total`. Orden descendente por fecha.
7. **La custodia no incluye secretos ni contenido**: no devuelve el hash a firmar de los desafíos, ni el cuerpo de los webhooks, ni PDF. Sí lista referencias (ids), fechas, estados, intentos y errores.
8. **Reenvío de webhook acotado a entregas `failed`**: restablece `status=pending`, `attempts=0` y `next_attempt_at=ahora`, y registra en `admin_event` los intentos previos para no perder el historial. Una entrega `delivered` o `pending` no se reenvía (`409`).
9. **Panel sin framework**: tres archivos estáticos servidos por FastAPI. Evita sumar otro proyecto de compilación para un panel de operación con seis tablas; el widget ya cubre la parte de interfaz con framework.

## Risks / Trade-offs

- Un único token compartido no distingue personas: la trazabilidad por persona queda para la integración con el directorio institucional.
- Quitar un ancla de confianza deja de validar nuevas firmas con esa cadena; es la intención y por eso queda en `admin_event`. Los documentos ya firmados no cambian.
- La destrucción de la clave vieja en disco es "lo mejor posible" (borrado de archivo, no borrado seguro de medio físico); con un HSM propio se resuelve de otra forma.
