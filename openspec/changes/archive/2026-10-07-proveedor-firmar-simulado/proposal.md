## Why

La propuesta incluye una tercera forma de firmar, además del token y del motor propio: la **firma remota** de un servicio tipo FirmAR/SIU, para usuarios con certificado remoto y no con token USB. Ahí la clave no está en la PC del usuario ni en Firmadoc: el servicio recibe el **documento completo**, el usuario autoriza allí (OTP + PIN) y el servicio devuelve el PDF firmado por una notificación (*callback*). Hoy `provider: firmar` se rechaza como "no habilitado". No hay convenio con el servicio real, por lo que se implementa el **adaptador completo contra un servicio simulado** que replica el contrato (OAuth, envío del documento, callback), de modo que reemplazarlo por el real sea cambiar URL y credenciales.

Backlog: FIRDOC-9 (autenticación OAuth simulada), FIRDOC-10 (enviar el documento y recibir la firma por callback) y la épica FIRDOC-2.

## What Changes

- **Proveedor `firmar`** (`firmar-provider`), habilitado cuando `FIRMADOC_FIRMAR_BASE_URL` está configurada:
  - `prepare` autentica contra el servicio (OAuth2 *client credentials*), envía el PDF de la versión vigente con el CUIL del firmante y la URL del callback, guarda el `operation_id` de la solicitud y la deja en `signing`; responde con los datos de la operación (`remote.operation_id`, `remote.authorization_url`) y sin desafíos.
  - `complete` no aplica (`409`, `remote_signature_pending`): la firma llega por callback.
  - **`POST /api/v1/providers/firmar/callback`** recibe el resultado, autenticado con una firma HMAC del cuerpo (`X-Firmar-Signature`), idempotente. Si el estado es `signed`, valida el PDF devuelto (que solo se haya **agregado** una firma al documento enviado, que su cadena llegue a las anclas, y que el **CUIL del certificado coincida con el del firmante**) y recién entonces crea la nueva `DocumentVersion`, igual que cualquier otra firma (versión inmutable, auditoría, webhook). Si es `rejected` o `expired`, la solicitud pasa a `failed`.
- **Servicio simulado** (`firmar-mock-service`), solo si `FIRMADOC_FIRMAR_MOCK_ENABLED=true` (desarrollo y pruebas): `POST /mock/firmar/oauth/token`, `POST /mock/firmar/v1/operations`, `GET …/{id}`, `POST …/{id}/approve` (simula OTP + PIN: firma el PDF con su propia AC y llama al callback) y `POST …/{id}/reject`. El límite de documentos por operación del servicio real **no está verificado**: el simulado admite uno por operación y queda documentado.
- Migración `0004`: `signature_request.remote_operation_id` (único).
- Refactor interno sin cambio de comportamiento: la creación de la versión firmada se extrae de `complete` para compartirla con el callback.

## Capabilities

### New Capabilities

- `firmar-provider`: adaptador de firma remota, callback y validación del PDF devuelto.
- `firmar-mock-service`: servicio simulado del contrato.

### Modified Capabilities

- `data-model`: columna `remote_operation_id`.

## Impact

- Servidor: `providers/firmar.py` (cliente), `services/remote_signing.py`, `mock_firmar.py`, rutas de callback y de la simulación, `signature_flow.py` (rama del proveedor y extracción de `_register_signed`), `providers/__init__.py`, `config.py`, `models.py`, migración `0004`.
- Variables de entorno nuevas: `FIRMADOC_FIRMAR_BASE_URL`, `FIRMADOC_FIRMAR_CLIENT_ID`, `FIRMADOC_FIRMAR_CLIENT_SECRET`, `FIRMADOC_FIRMAR_CALLBACK_SECRET`, `FIRMADOC_FIRMAR_TIMEOUT_SECONDS`, `FIRMADOC_FIRMAR_MOCK_ENABLED`.
- Documentación: `docs/firmar.md` con el contrato simulado, qué cambiar para el servicio real y los supuestos.

## Fuera de alcance

- La pantalla del widget para firma remota (redirigir a `authorization_url` y esperar el resultado): depende de elegir el proveedor desde el widget (FIRDOC-12, otro cambio). El adaptador es plenamente utilizable por API.
- Lotes con `firmar` y el soporte del servicio real (límite de documentos, esquema exacto de campos): se ajustan cuando exista el convenio.
- Revocación del certificado del servicio remoto al aceptar el PDF (se valida la cadena y el CUIL; la revocación queda como en `verify`).
