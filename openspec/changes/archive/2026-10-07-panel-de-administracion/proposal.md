## Why

Hoy no hay forma de operar Firmadoc sin entrar a la base: no se puede ver quién firmó qué y cuándo (FIRDOC-14), reconstruir la cadena de custodia de un documento (FIRDOC-15), reenviar un webhook fallido, gestionar las anclas de confianza ni rotar el certificado propio ante un compromiso (FIRDOC-27). Todo el material ya está guardado (solicitudes, versiones, auditoría, desafíos, entregas), pero no se expone, y los cambios de confianza hoy exigen tocar archivos a mano sin dejar rastro.

Backlog: FIRDOC-14 (HU4), FIRDOC-15, FIRDOC-27 (HU11) y la épica FIRDOC-4.

## What Changes

- **Acceso de administración** (`admin-access`): un token de administración (`FIRMADOC_ADMIN_TOKEN`, mínimo 32 caracteres) en `Authorization: Bearer`, comparado en tiempo constante. Sin token configurado, la administración queda deshabilitada. Toda acción que **modifica** algo (reenviar un webhook, agregar o quitar un ancla, rotar el certificado) queda en una tabla nueva `admin_event`, append-only a nivel de base de datos (migración `0003`).
- **Historial de firmas** (`admin-audit-views`): listado paginado de solicitudes con filtros por integrador, estado, proveedor, firmante y fechas, que incluye el estado del documento y su versión vigente (FIRDOC-14).
- **Cadena de custodia** (`admin-audit-views`): para un documento, todas sus versiones, la vigente, las solicitudes con sus eventos, los desafíos y las entregas de webhook (FIRDOC-15).
- **Webhooks** (`admin-audit-views`): listado de entregas con su estado y reenvío de una entrega fallida.
- **Anclas de confianza y certificado propio** (`trust-management`): listar, agregar y quitar anclas de `FIRMADOC_TRUST_DIR`; rotar el certificado propio del proveedor `local` conservando su parte pública para que las firmas ya emitidas sigan verificándose (FIRDOC-27).
- **Panel web** (`admin-panel`): página `/admin` (HTML, CSS y JS propios, sin dependencias ni scripts en línea, con CSP estricta) que consume esa API: solicitudes, custodia, webhooks, anclas, certificado y eventos de administración.

## Capabilities

### New Capabilities

- `admin-access`: autenticación de administración y registro inmutable de acciones.
- `admin-audit-views`: historial de firmas, cadena de custodia y entregas de webhook.
- `trust-management`: anclas de confianza y rotación del certificado propio.
- `admin-panel`: la página web de administración.

### Modified Capabilities

- `data-model`: tabla `admin_event` (append-only).
- `certificate-validation`: la verificación de documentos incluye los certificados propios archivados.

## Impact

- Servidor: `admin_auth`, `services/admin.py`, `api/admin_routes.py`, `api/admin_pages.py`, `admin_ui/` (estáticos), modelo `AdminEvent`, migración `0003`, ajustes en `trust.py` y `providers/local.py` (rotación) y en `services/documents.py` (anclas archivadas).
- Variable de entorno nueva: `FIRMADOC_ADMIN_TOKEN`.
- Documentación: `docs/admin.md`.

## Fuera de alcance

- Usuarios y roles de administración, SSO o doble factor: un solo token de administración compartido por quien opera el servicio. Se anota como evolución (integración con el directorio institucional).
- Revocación de certificados de firmantes y consulta/descarga de PDF desde el panel.
- Limitar intentos de acceso por IP (el token es aleatorio de 32 o más caracteres; el límite corresponde al proxy inverso).
- Un cambio de anclas aplica a las siguientes validaciones; los procesos con la copia en memoria la ven al reiniciar si se editó el directorio fuera de la API.
