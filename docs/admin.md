# Administración

## Habilitar

Definir `FIRMADOC_ADMIN_TOKEN` (mínimo 32 caracteres; generar con
`python -c "import secrets; print(secrets.token_urlsafe(32))"`). Sin él, toda la administración responde `404`.
El token es **distinto** de las API keys de integrador y no las reemplaza. Panel: `https://<servidor>/admin`.

Todas las rutas de la API usan `Authorization: Bearer <token>`.

## API (`/api/v1/admin`)

| Ruta | Para qué |
|---|---|
| `GET /signature-requests` | Historial con filtros `integrating_system_id`, `status`, `provider`, `signer` (CUIL exacto o texto del nombre), `created_from`, `created_to`, `limit` (≤ 200), `offset`; devuelve `total` |
| `GET /documents/{id}/custody` | Versiones, solicitudes con eventos, desafíos y entregas de webhook (sin hashes a firmar ni cuerpos) |
| `GET /webhook-deliveries` · `POST /webhook-deliveries/{id}/retry` | Entregas y reenvío de las fallidas |
| `GET/POST /trust-anchors` · `DELETE /trust-anchors/{huella}` | Anclas de confianza (PEM de una sola CA o certificado autofirmado vigente) |
| `GET /local-certificate` · `POST /local-certificate/rotate` | Certificado propio del proveedor `local` |
| `GET /events` | Acciones de administración registradas |

## Qué queda registrado

Las acciones que **modifican** algo (reenviar un webhook, agregar/quitar un ancla, rotar el certificado) se
guardan en `admin_event`, una tabla append-only a nivel de base de datos (no admite `UPDATE` ni `DELETE`).
Las lecturas no se registran.

## Rotación del certificado propio

El certificado público vigente se archiva en `<FIRMADOC_LOCAL_CERT_DIR>/archive/` y la clave privada vieja
**se borra**. Las firmas anteriores siguen verificándose con `POST /documents/{id}/verify` porque el certificado
archivado se usa como ancla. Las firmas `local` que estaban preparadas pero sin completar durante la rotación
fallan y deben solicitarse de nuevo.

Limitación: tras un compromiso de la clave, una firma antigua no se puede distinguir de una forjada con la clave
robada hasta que exista sello de tiempo de una TSA (cambio de sello de tiempo).

## Anclas de confianza con varias réplicas

Agregar o quitar un ancla se aplica de inmediato en el proceso que atiende el pedido. Con varias réplicas todas
deben compartir el directorio `FIRMADOC_TRUST_DIR` (volumen compartido) y las demás lo toman al reiniciar.

## Seguridad del panel

CSP `script-src 'self'` sin scripts ni estilos en línea, `frame-ancestors 'none'`, `no-store`; el contenido se
construye siempre como texto; el token vive en `sessionStorage` (se borra al cerrar la pestaña) y no se usan
cookies. Un único token compartido no distingue personas: la identidad individual queda para una integración
con el directorio institucional. Limitar intentos de acceso por IP corresponde al proxy inverso.
