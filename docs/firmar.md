# Firma remota (`firmar`) — adaptador y servicio simulado

El proveedor `firmar` delega la firma en un servicio remoto (tipo FirmAR/SIU): el servicio recibe el **PDF
completo**, el usuario autoriza allí (OTP + PIN) y el servicio devuelve el PDF firmado por un *callback*. La
clave nunca pasa por Firmadoc. No hay convenio con el servicio real: el contrato está **simulado**.

## Configuración

| Variable | Significado |
|---|---|
| `FIRMADOC_FIRMAR_BASE_URL` | URL base del servicio. **Sin ella el proveedor no está habilitado** (`422`) |
| `FIRMADOC_FIRMAR_CLIENT_ID` / `FIRMADOC_FIRMAR_CLIENT_SECRET` | Credenciales OAuth2 *client credentials* |
| `FIRMADOC_FIRMAR_CALLBACK_SECRET` | Secreto compartido (≥ 32 caracteres) para firmar el callback |
| `FIRMADOC_FIRMAR_TIMEOUT_SECONDS` | Tiempo límite hacia el servicio (10) |
| `FIRMADOC_FIRMAR_MOCK_ENABLED` | `true` monta el servicio simulado en `/mock/firmar` (solo desarrollo y pruebas) |

Para probar todo en un solo servidor: `FIRMAR_BASE_URL=http://localhost:8000/mock/firmar`, `MOCK_ENABLED=true`,
un `CLIENT_SECRET` y un `CALLBACK_SECRET`. La AC del simulado se suma sola a las anclas de verificación.
**El modo demostración (`python -m firmadoc.demo`) ya lo configura así**, con secretos generados una vez en
`data/demo/demo.json` (`demo.md`, «Firma remota con el servicio simulado»).

## Flujo

1. El integrador crea la solicitud con `provider: firmar` y llama a `prepare` (`/prepare`).
2. Firmadoc obtiene un token (`POST {base}/oauth/token`) y envía el PDF vigente
   (`POST {base}/v1/operations` con `document_base64`, `signer_cuil`, `callback_url`).
   La respuesta de `prepare` trae `challenges: []` y `remote: {operation_id, authorization_url}`.
   `complete` no aplica: `409 remote_signature_pending`.
3. El usuario autoriza en el servicio. En el simulado hay dos caminos equivalentes: la **página de
   autorización** de la `authorization_url` (`GET /mock/firmar/authorize/{id}`, la que abre el widget con
   «Continuar en el servicio de firma»: formulario con OTP y PIN y botón «Rechazar», sin token OAuth porque es la
   pantalla del usuario y no una ruta de la API), o por API: `POST /mock/firmar/v1/operations/{id}/approve` con
   `{"otp": "123456", "pin": "1234"}` o `…/reject`. En ambos, 3 fallos bloquean la operación.
4. El servicio llama a `POST /api/v1/providers/firmar/callback` con
   `{"operation_id", "status": "signed"|"rejected"|"expired", "signed_document_base64"}` y la cabecera
   `X-Firmar-Signature: sha256=<HMAC-SHA256 del cuerpo crudo con el secreto del callback>`.

## Qué valida Firmadoc del PDF devuelto

Un mensaje auténtico no basta: antes de crear la versión se exige que el PDF **comience con los mismos bytes**
de la versión enviada (solo se agregó una actualización incremental), que tenga **exactamente una firma más**,
que esa firma sea íntegra y su cadena llegue a las **anclas de confianza** (el certificado del servicio real
debe agregarse como ancla desde el panel de administración) y que el **CUIL del certificado coincida** con el del
firmante. Si algo falla, la solicitud pasa a `failed` (con `code`) y el callback responde `422`. El callback es
idempotente (`already_processed`).

## Pasar al servicio real

Cambiar `FIRMADOC_FIRMAR_BASE_URL` y las credenciales, agregar su AC como ancla y revisar los **supuestos del
simulado** (a verificar con el servicio): rutas y nombres de campos, autenticación del callback (aquí HMAC),
un documento por operación (el servicio real limitaría la cantidad por operación: valor sin verificar) y que
el PDF firmado extienda al enviado. Esas diferencias se concentran en `providers/firmar.py` y
`services/remote_signing.py`.

## Límites

- Sin lotes con `firmar`. El estado del simulado vive en memoria (se pierde al reiniciar el servidor).
- La revocación del certificado remoto no se consulta al aceptar el PDF.
