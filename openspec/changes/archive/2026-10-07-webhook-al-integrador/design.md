## Context

`callback_url` ya viaja en `POST /signature-requests` y se descarta. El modelo ya tiene `WebhookDelivery` (url, estado, intentos, último intento) pero sin uso. El flujo de firma termina en dos lugares (`complete` exitoso y `_fail`), y ahí nace la notificación. Hay que decidir cómo se garantiza la entrega (la transacción de firma no puede perder el aviso), cómo se autentica ante el integrador y cómo se evita que Firmadoc sea usado para atacar la red interna (SSRF).

## Goals / Non-Goals

**Goals:** entrega confiable (al menos una vez), verificable por el integrador, segura contra SSRF, sin dependencias de infraestructura nueva, y con el estado de cada intento consultable.

**Non-Goals:** cola externa, panel de reenvío, otros eventos, lotes (ver proposal).

## Decisions

1. **Patrón *outbox*: la entrega se registra en la misma transacción que la firma** y un trabajador la envía después. Si el servidor cae justo después de firmar, el aviso no se pierde; si la transacción falla, no queda ningún aviso huérfano. Alternativa descartada: enviar el HTTP dentro del `complete` (acopla la latencia y la disponibilidad del integrador al flujo de firma) o con `BackgroundTasks` (se pierde si el proceso cae antes de ejecutarse).
2. **Garantía "al menos una vez"**: el integrador puede recibir el mismo evento más de una vez (p. ej. respondió `200` pero la respuesta se perdió). Cada pedido lleva `X-Firmadoc-Delivery` (id estable de la entrega) para deduplicar. Se documenta en `docs/webhooks.md`.
3. **Cuerpo fijo y firma por intento**: el cuerpo JSON se serializa **una vez** (claves ordenadas, separadores compactos) al crear la entrega y se guarda como texto; los reintentos reenvían exactamente esos bytes. La firma `t=<epoch>,v1=<hmac>` se recalcula en cada intento con la hora de ese intento, para que el integrador pueda rechazar repeticiones antiguas (ventana de tolerancia recomendada: 5 minutos).
4. **HMAC-SHA256 con un secreto por integrador** (`webhook_secret`), separado de la API key. La API key solo se guarda como hash (no se puede usar para firmar); el secreto de webhook sí se guarda para poder firmar, por eso es un valor distinto, rotable sin invalidar la API key. Alternativas descartadas: firmar con la API key (no recuperable) o con una clave asimétrica (más seguro frente a filtración de la base, pero obliga al integrador a gestionar claves públicas; queda como evolución). Se guarda en claro en la base: el riesgo (quien lea la base puede falsificar webhooks de ese integrador) se documenta y se mitiga en la base PostgreSQL real con cifrado a nivel de columna.
5. **Reintentos con *backoff* fijo** `[30 s, 2 min, 10 min, 1 h, 6 h]` (seis intentos en total, unas 7 h 12 min). `next_attempt_at` indica cuándo toca el siguiente. Sin *jitter*: con un solo trabajador no hace falta.
6. **Reserva (*lease*) de entregas sin estado nuevo**: el trabajador "reclama" una entrega con `UPDATE … SET next_attempt_at = now + 60 s WHERE id = ? AND status = 'pending' AND next_attempt_at <= now` y solo envía si `rowcount == 1`. Dos ejecuciones concurrentes no duplican el envío, y si el proceso cae a mitad, la reserva vence y se reintenta. Se evita agregar un estado `sending` (obligaría a modificar la restricción CHECK del enum). Con varias réplicas el `UPDATE` condicional sigue siendo correcto (es atómico); no hace falta `SKIP LOCKED`.
7. **Trabajador = un hilo del propio servidor** (arrancado en el *lifespan* de FastAPI, apagable con `FIRMADOC_WEBHOOK_WORKER_ENABLED=false`), con su propia sesión de base y que resuelve la configuración como la API (respetando los reemplazos de dependencias de las pruebas). `run_due(db, now)` es la unidad probable sin hilos ni esperas.
8. **SSRF por capas**:
   - *Al crear la solicitud*: esquema `https` (`http` solo con `FIRMADOC_WEBHOOK_ALLOW_HTTP`), sin credenciales en la URL, host obligatorio y **todas** las direcciones a las que resuelve deben ser globales (`ipaddress.is_global`; cubre privadas, loopback, enlace local, CGNAT, reservadas y multicast; las IPv6 mapeadas a IPv4 se evalúan como IPv4). `FIRMADOC_WEBHOOK_ALLOW_PRIVATE_HOSTS` salta el control de direcciones (solo desarrollo y pruebas).
   - *Al entregar*: se vuelve a resolver y validar justo antes de enviar (DNS puede cambiar), sin seguir redirecciones, con tiempo límite y sin leer el cuerpo de la respuesta (no se necesita, y evita agotar memoria).
   - **Límite conocido:** queda una ventana mínima entre la validación y la conexión (*TOCTOU* de DNS). Cerrarla del todo exige fijar la IP en la conexión con un *network backend* propio de httpx/httpcore; se anota como mejora. La mitigación práctica es que la respuesta nunca se lee ni se devuelve a nadie, por lo que un SSRF "ciego" solo permitiría un `POST` con cuerpo fijo hacia la red interna.
9. **Línea de comandos de integradores** en vez de endpoints administrativos: no existe todavía un modelo de administradores (llega con el panel). La CLI usa la base directamente, genera valores con `secrets`, muestra los secretos **una sola vez** y nunca los vuelve a mostrar (`list` no los imprime).
10. **Migración `0002` manual** (no autogenerada): `add_column` nullable en tres tablas, sin tocar triggers; `downgrade` con `batch_alter_table` para SQLite.
11. **`httpx` como dependencia de runtime** (ya se usaba en pruebas): cliente síncrono con `follow_redirects=False`.
12. **Cuerpos distintos para `signed` y `failed`**: el de `failed` solo trae un `code` estable (el mismo que el widget conoce), nunca el detalle de la excepción; el de `signed` trae `download_url` (que exige API key para descargar) en lugar del PDF.

## Risks / Trade-offs

- **Secreto de webhook en claro en la base** (ver decisión 4).
- **Hilo en el mismo proceso**: si el servidor se reinicia, las entregas pendientes se retoman al volver (están en la base), con un retraso de hasta el intervalo de sondeo.
- **Integrador lento**: el trabajador es secuencial; un integrador que tarda `timeout` en cada pedido retrasa a los demás. Mitigación: tiempo límite corto (5 s) y entregas en paralelo limitado como mejora futura.
- **Resolución DNS bloqueante** dentro del hilo: tolerable por el volumen esperado.
- **Repeticiones**: "al menos una vez" exige que el integrador sea idempotente (documentado, con `X-Firmadoc-Delivery`).

## Open Questions

- ¿Hace falta un reenvío manual? Se resuelve con el panel de administración.
- ¿Firma asimétrica (Ed25519) en lugar de HMAC? Evaluar si algún integrador no puede custodiar un secreto compartido.
