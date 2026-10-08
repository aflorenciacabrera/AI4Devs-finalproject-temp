## 1. Esquema y configuración

- [x] 1.1 Agregar al modelo `SignatureRequest.callback_url`, `IntegratingSystem.webhook_secret` y a `WebhookDelivery` el evento, el cuerpo (texto), `next_attempt_at`, `last_error`, `response_status` y `created_at`
- [x] 1.2 Escribir la migración `0002` (reversible, conserva datos, no toca los triggers) y probar `upgrade`, `downgrade` y `upgrade` sobre datos existentes
- [x] 1.3 Agregar `webhook_allow_http`, `webhook_allow_private_hosts`, `webhook_timeout_seconds` (5), `webhook_worker_enabled` (true) y `webhook_poll_seconds` (5) a `Settings` y a `.env.example`; pasar `httpx` a dependencia de runtime
- [x] 1.4 Tests de la migración y del esquema (columnas, datos previos, triggers intactos)

## 2. Validación de la URL

- [x] 2.1 Implementar `validate_callback_url` (esquema, credenciales, host, longitud y todas las direcciones resueltas deben ser globales, incluidas IPv6 mapeadas a IPv4) con resolución inyectable
- [x] 2.2 Validar `callback_url` al crear la solicitud (`422` con `code: invalid_callback_url`, sin crear nada) y guardarla
- [x] 2.3 Tests: https público, http, esquemas raros, credenciales, `localhost`, `127.0.0.1`, `10.x`, `169.254.169.254`, `100.64.x`, IPv6 `::1` y mapeadas, nombre que resuelve a privada, fallo de DNS, y que no se cree documento al rechazar

## 3. Entregas

- [x] 3.1 Implementar la construcción del cuerpo (eventos `signature.signed` y `signature.failed`, sin PDF ni credenciales), serializado una sola vez
- [x] 3.2 Registrar la entrega en la misma transacción al pasar la solicitud a `signed` y a `failed` (solo si hay `callback_url`)
- [x] 3.3 Implementar la firma `X-Firmadoc-Signature` (HMAC-SHA256 sobre `t.cuerpo`) y las cabeceras `X-Firmadoc-Event` y `X-Firmadoc-Delivery`
- [x] 3.4 Implementar `deliver`: revalidar el host, enviar sin redirecciones, con tiempo límite y sin leer la respuesta; actualizar intentos, `last_error`, `response_status` y el siguiente intento con el backoff; marcar `failed` tras el sexto intento
- [x] 3.5 Implementar `run_due` con la reserva atómica (lease) y los eventos de auditoría `webhook_delivered` / `webhook_failed`
- [x] 3.6 Tests con un servidor HTTP local: éxito, 500 y recuperación, agotamiento de los seis intentos con el reloj controlado, tiempo agotado, redirección, host que pasa a privado entre medio, integrador sin secreto, cuerpo idéntico entre reintentos, `t` distinto y firma verificable por quien recibe, entrega futura no enviada, y dos `run_due` simultáneos sin duplicar
- [x] 3.7 Test de atomicidad: si falla la transacción de la firma no queda entrega

## 4. Trabajador

- [x] 4.1 Hilo en el *lifespan* de FastAPI, apagable por configuración, con su propia sesión y la configuración resuelta como en la API; apagado ordenado
- [x] 4.2 Test del trabajador: arranca, entrega una pendiente vencida y se detiene sin dejar hilos

## 5. Integradores

- [x] 5.1 Implementar `python -m firmadoc.integrators` con `create`, `rotate-webhook-secret` y `list` (generación con `secrets`, secretos mostrados una sola vez, solo hash de la API key, orígenes validados, nombre único)
- [x] 5.2 Actualizar el seed con un secreto de webhook de demostración
- [x] 5.3 Tests: alta, orígenes inválidos, nombre repetido, que solo exista el hash, rotación (la API key sigue valiendo y las entregas nuevas usan el secreto nuevo) y que el listado no imprima secretos

## 6. Flujo de punta a punta y documentación

- [x] 6.1 Prueba de punta a punta con la API real: crear solicitud con `callback_url`, firmar con `local` y comprobar que el receptor local recibe el evento firmado verificable
- [x] 6.2 Escribir `docs/webhooks.md` (contenido, verificación de la firma con ejemplos en Python y Node, idempotencia, reintentos, seguridad de la URL) y enlazarlo desde `backend/README.md`
- [x] 6.3 Ejecutar `pytest` y `ruff check` sin errores
