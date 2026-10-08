## Why

Hoy el sistema integrador solo se entera de que un documento se firmó si consulta la solicitud (`GET /signature-requests/{id}`) o recibe el mensaje del navegador, que no es confiable (la persona puede cerrar la pestaña, el navegador puede fallar). `callback_url` ya se acepta en `POST /signature-requests` pero se descarta. Falta la notificación **de servidor a servidor**: cuando una solicitud termina (`signed` o `failed`), Firmadoc avisa al integrador con un pedido HTTP firmado y reintenta si el integrador no responde.

Backlog: FIRDOC-24 (HU3, webhook al integrador).

## What Changes

- **Entrega de webhooks** (`webhook-delivery`): al pasar una solicitud a `signed` o `failed`, Firmadoc registra una entrega y hace `POST {callback_url}` con el bloque `document` (descarga y versión) o el motivo del fallo. Reintenta con *backoff* (30 s, 2 min, 10 min, 1 h, 6 h) hasta 6 intentos y deja cada intento en `WebhookDelivery`.
- **Autenticidad**: cada pedido lleva `X-Firmadoc-Signature: t=<epoch>,v1=<HMAC-SHA256(secreto, "<t>.<cuerpo>")>`, para que el integrador verifique que lo envió Firmadoc, que el cuerpo no se alteró y que no es una repetición vieja. El secreto es propio de cada integrador (`webhook_secret`).
- **Protección contra SSRF**: `callback_url` debe ser `https` (con excepción configurable para desarrollo), no puede apuntar a direcciones privadas, de loopback ni de enlace local (se revisa al crear la solicitud **y** al entregar, resolviendo el DNS), no sigue redirecciones y tiene tiempo límite.
- **Gestión de integradores** (`integrator-management`): una pequeña línea de comandos `python -m firmadoc.integrators` crea integradores (API key y secreto de webhook, mostrados una sola vez; se guarda solo el hash de la key) y rota el secreto de webhook. Hasta ahora no había forma de crear integradores fuera del seed.
- **Trabajador en segundo plano** que entrega las notificaciones pendientes al arrancar el servidor, con un `run_due` invocable directamente (también en pruebas).
- `callback_url` se valida, se guarda en la solicitud y los eventos `webhook_delivered` / `webhook_failed` quedan en la auditoría.
- Migración `0002`: `signature_request.callback_url`, `integrating_system.webhook_secret` y las columnas de reintento de `webhook_delivery`.

## Capabilities

### New Capabilities

- `webhook-delivery`: contenido, firma, reintentos y seguridad de las notificaciones al integrador.
- `integrator-management`: alta de integradores y rotación del secreto de webhook por línea de comandos.

### Modified Capabilities

- `signature-requests`: `callback_url` se valida y se conserva; la transición a `signed`/`failed` genera la notificación.
- `data-model`: columnas nuevas de webhook (requisito agregado).

## Impact

- Servidor: `webhooks.py` (entrega, firma, SSRF), `integrators.py` (CLI), cambios en `signature_flow.py`, `models.py`, `config.py`, `main.py` (trabajador) y una migración Alembic.
- Dependencia: `httpx` pasa de dependencia de desarrollo a dependencia del servidor.
- Variables de entorno nuevas: `FIRMADOC_WEBHOOK_ALLOW_HTTP`, `FIRMADOC_WEBHOOK_ALLOW_PRIVATE_HOSTS` (solo desarrollo/pruebas), `FIRMADOC_WEBHOOK_TIMEOUT_SECONDS`, `FIRMADOC_WEBHOOK_WORKER_ENABLED`, `FIRMADOC_WEBHOOK_POLL_SECONDS`.
- Documentación: guía de verificación de la firma del webhook para el integrador (con ejemplos en Python y Node/Angular) en `docs/webhooks.md`.

## Fuera de alcance

- Cola externa (Redis, RabbitMQ): el trabajador es un hilo del propio servidor sobre la tabla `webhook_delivery`. Con varias réplicas hará falta un bloqueo (`SELECT … FOR UPDATE SKIP LOCKED`); se deja anotado y se implementa con la base PostgreSQL real.
- Panel para ver y reenviar entregas (change del panel de administración).
- Eventos distintos de `signature.signed` y `signature.failed` (por ejemplo, vencimiento del plazo).
- Webhooks para lotes (change de firma en lote).
- Varias URL por integrador o por evento: una `callback_url` por solicitud.
