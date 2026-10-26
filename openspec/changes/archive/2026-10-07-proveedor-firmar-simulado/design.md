## Context

`token` y `local` firman un **hash** con el motor PAdES propio. La firma remota es otra familia: el servicio recibe el **PDF completo**, firma con una clave que Firmadoc nunca ve y devuelve el PDF firmado. No hay desafío, ni agente, ni `complete` iniciado por el cliente. El servicio real no es accesible (requiere convenio), por lo que el contrato se simula.

## Goals / Non-Goals

**Goals:** que el flujo remoto sea un proveedor más (misma solicitud, mismas versiones, auditoría y webhooks); que **no se confíe a ciegas** en lo que devuelve un tercero; que pasar al servicio real implique cambiar configuración.

**Non-Goals:** UI en el widget, lotes remotos (ver proposal).

## Decisions

1. **Asíncrono por callback.** `prepare` envía el documento y deja la solicitud en `signing`; el resultado entra por `POST /api/v1/providers/firmar/callback`. Alternativa descartada: *polling* al servicio: el contrato descrito usa callback y evita consultas periódicas.
2. **El callback no confía en el cuerpo, valida el PDF.** La autenticidad del mensaje se prueba con HMAC-SHA256 del cuerpo crudo (`X-Firmar-Signature: sha256=<hex>`, secreto compartido `FIRMADOC_FIRMAR_CALLBACK_SECRET`, comparación en tiempo constante). Pero un mensaje auténtico igual puede traer un PDF indebido (un error del servicio, o un servicio comprometido), así que antes de crear la versión se exige: (a) que el PDF devuelto **empiece exactamente con los bytes** de la versión vigente (solo actualización incremental: nada del documento original cambió), (b) que haya **exactamente una firma más**, (c) que esa firma sea íntegra y su cadena llegue a las **anclas de confianza**, y (d) que el **CUIL del certificado coincida con el del firmante** de la solicitud (un tercero no puede firmar "como" otra persona). Cualquier falla marca la solicitud `failed` con el motivo y responde `422`.
3. **Idempotencia**: el servicio puede reenviar el callback. Si la solicitud ya está `signed` o `failed`, responde `200` con `status: already_processed` sin crear nada. La búsqueda es por `remote_operation_id` (columna única, migración `0004`), no por un id que mande el servicio para elegir otra solicitud.
4. **Autenticación saliente OAuth2 *client credentials*** (`client_id` + `client_secret` por configuración) contra `{base}/oauth/token`, con un token nuevo por operación (simple y sin estado; el costo es una llamada más por firma). Los errores del servicio (red, 4xx/5xx, credenciales) se informan como `503` genérico (`remote_unavailable`) sin reproducir cuerpos del servicio.
5. **Servicio simulado dentro del mismo servidor, solo con bandera**. Una AC propia del simulado emite un certificado con `serialNumber=CUIL <cuil>` por operación y firma con pyHanko; al aprobar llama al callback con HMAC. Al estar habilitado, su AC se suma a las anclas de verificación (para que la demo funcione sin configurar nada); con la bandera apagada, no existe ninguna ruta `/mock/firmar` (`404`) ni ancla. El estado de las operaciones vive en memoria del proceso: es un simulador.
6. **Transporte HTTP inyectable** (`httpx` con `transport` reemplazable) para que las pruebas conecten Firmadoc, el simulado y el callback sin red y también contra un servidor real local.
7. **Refactor mínimo de `signature_flow`**: la parte de `complete` que crea la `DocumentVersion`, actualiza el estado, audita y registra el webhook se extrae a `_register_signed` para usarla desde el callback. No cambia comportamiento; la cubren las pruebas existentes.
8. **`prepare` de `firmar` no crea `SigningChallenge`.** La respuesta lleva `challenges: []` y un bloque `remote`. `complete` responde `409` con `code: remote_signature_pending`.

## Risks / Trade-offs

- El contrato real puede diferir (nombres de campos, autenticación del callback, firma del PDF por el servicio); el adaptador y el simulado concentran esas diferencias en dos módulos pequeños y en `docs/firmar.md`.
- Que el PDF devuelto deba extender byte a byte el enviado puede rechazar a un servicio que reescriba el archivo; es una exigencia deliberada (integridad del contenido) y se documenta.
- El estado en memoria del simulado se pierde al reiniciar: las operaciones en curso quedan huérfanas (solo desarrollo).
