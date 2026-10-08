## ADDED Requirements

### Requirement: Notificación al terminar la solicitud
Cuando una `SignatureRequest` con `callback_url` pasa a `signed` o a `failed`, Firmadoc SHALL registrar una `WebhookDelivery` en estado `pending` en la **misma transacción** que el cambio de estado, y SHALL notificar al integrador con `POST {callback_url}`; si no hay `callback_url` no se registra ninguna entrega.

#### Scenario: Firma completada
- **WHEN** la solicitud pasa a `signed`
- **THEN** existe una entrega `pending` con el evento `signature.signed`

#### Scenario: Firma fallida
- **WHEN** la solicitud pasa a `failed`
- **THEN** existe una entrega `pending` con el evento `signature.failed`

#### Scenario: Sin callback
- **WHEN** la solicitud no tiene `callback_url`
- **THEN** no se registra ninguna entrega

#### Scenario: Atomicidad
- **WHEN** falla la transacción que completa la firma
- **THEN** no queda ninguna entrega registrada

### Requirement: Contenido de la notificación
El cuerpo SHALL ser JSON con `event`, `delivery_id`, `created_at`, los datos de la solicitud (`id`, `status`, `provider`, `external_document_id`) y, para `signature.signed`, el bloque `document` (`id`, `version_number`, `is_active_version`, `signing_status`, `signature_level`, `download_url`) y el `certificate` (`subject`, `issuer_subject`, `serial_number`); para `signature.failed`, un `error` con `code` sin detalles internos. SHALL NOT incluir el PDF ni credenciales.

#### Scenario: Evento firmado
- **WHEN** se notifica una firma completada
- **THEN** el cuerpo trae `document.version_number`, `document.is_active_version: true` y `download_url`, y no trae `signed_document_base64`

#### Scenario: Evento fallido
- **WHEN** se notifica un fallo
- **THEN** el cuerpo trae `error.code` y ningún mensaje de excepción ni traza

#### Scenario: Cuerpo estable entre reintentos
- **WHEN** una entrega se reintenta
- **THEN** el cuerpo enviado es idéntico byte a byte al del primer intento

### Requirement: Firma de autenticidad
Cada pedido SHALL llevar `X-Firmadoc-Signature: t=<epoch>,v1=<hex>` con `v1 = HMAC-SHA256(webhook_secret, "<t>.<cuerpo>")`, más `X-Firmadoc-Event` y `X-Firmadoc-Delivery`; el secreto SHALL ser el del integrador de la solicitud y SHALL NOT viajar nunca en el pedido.

#### Scenario: Verificación por el integrador
- **WHEN** el integrador recalcula el HMAC con su secreto sobre `t` y el cuerpo recibido
- **THEN** coincide con `v1`

#### Scenario: Marca de tiempo por intento
- **WHEN** se reintenta una entrega
- **THEN** `t` corresponde al momento de ese intento (permite al integrador rechazar repeticiones antiguas) y `v1` se recalcula

#### Scenario: Integrador sin secreto
- **WHEN** el integrador no tiene `webhook_secret`
- **THEN** la entrega no se envía, queda `failed` con el motivo `missing_secret` y se registra el evento de auditoría

### Requirement: Reintentos con backoff
Si el integrador no responde `2xx`, Firmadoc SHALL reintentar a los 30 segundos, 2 minutos, 10 minutos, 1 hora y 6 horas, SHALL registrar cada intento (`attempts`, `last_attempt_at`, `last_error`, `response_status`) y SHALL marcar la entrega `failed` tras el sexto intento fallido.

#### Scenario: Éxito al primer intento
- **WHEN** el integrador responde `204`
- **THEN** la entrega queda `delivered` con `attempts = 1`

#### Scenario: Falla y recupera
- **WHEN** el integrador responde `500` y luego `200`
- **THEN** el primer intento programa el siguiente según el backoff y el segundo deja la entrega `delivered` con `attempts = 2`

#### Scenario: Agotamiento
- **WHEN** fallan los seis intentos
- **THEN** la entrega queda `failed`, no se reintenta más y se registra el evento `webhook_failed`

#### Scenario: Error de red o tiempo agotado
- **WHEN** el integrador no responde dentro del tiempo límite
- **THEN** cuenta como intento fallido con `last_error` descriptivo y sin cuerpo de la respuesta

### Requirement: Protección contra SSRF
`callback_url` SHALL ser `https` (salvo que `FIRMADOC_WEBHOOK_ALLOW_HTTP` lo permita), SHALL rechazarse si su host es o resuelve a una dirección privada, de loopback, de enlace local, multicast o reservada (salvo `FIRMADOC_WEBHOOK_ALLOW_PRIVATE_HOSTS`), SHALL NOT incluir credenciales en la URL, y la entrega SHALL volver a resolver y validar el host, no seguir redirecciones y limitar el tamaño y el tiempo de la respuesta.

#### Scenario: Dirección privada
- **WHEN** `callback_url` apunta a `https://10.0.0.5/hook` o a un nombre que resuelve a `127.0.0.1`
- **THEN** se rechaza al crear la solicitud con `422` y código `invalid_callback_url`

#### Scenario: Esquema no permitido
- **WHEN** `callback_url` es `http://…`, `file://…` o `ftp://…`
- **THEN** se rechaza con `422`

#### Scenario: Credenciales en la URL
- **WHEN** `callback_url` es `https://usuario:clave@host/hook`
- **THEN** se rechaza con `422`

#### Scenario: DNS rebinding
- **WHEN** el host resolvía a una dirección pública al crear la solicitud pero resuelve a una privada al entregar
- **THEN** la entrega no se envía y cuenta como intento fallido

#### Scenario: Redirección
- **WHEN** el integrador responde `302`
- **THEN** no se sigue la redirección y el intento cuenta como fallido

### Requirement: Trabajador de entregas
El servidor SHALL procesar las entregas `pending` cuyo `next_attempt_at` venció, sin duplicar una entrega que ya se está enviando, mediante un trabajador en segundo plano activable por configuración y una función `run_due` invocable directamente.

#### Scenario: Entrega vencida
- **WHEN** hay una entrega con `next_attempt_at` en el pasado
- **THEN** `run_due` la envía y actualiza su estado

#### Scenario: Entrega futura
- **WHEN** la entrega tiene `next_attempt_at` en el futuro
- **THEN** `run_due` no la envía todavía

#### Scenario: Sin duplicados
- **WHEN** dos ejecuciones de `run_due` coinciden sobre la misma entrega
- **THEN** se envía una sola vez

### Requirement: Auditoría de las entregas
Cada resultado terminal de una entrega SHALL registrar un `AuditEvent` de la solicitud: `webhook_delivered` o `webhook_failed`, con el número de intentos y sin el cuerpo ni el secreto.

#### Scenario: Entregado
- **WHEN** una entrega se completa
- **THEN** la solicitud tiene un evento `webhook_delivered` con `attempts`
