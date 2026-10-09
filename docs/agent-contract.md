# Contrato entre Firmadoc y el agente local

Este documento fija lo que el **agente local** (`agent/`, FIRDOC-21) y el **servidor** esperan el uno del otro en el flujo de firma con token (proveedor `token`). El simulador `tests/agent_simulator.py` lo implementa y es la referencia ejecutable.

## Principios

- El agente **solo lista certificados públicos y firma hashes**. No descarga el PDF, no tiene credenciales de Firmadoc ni se conecta con el servidor.
- El PIN lo ingresa el usuario en la PC, en el diálogo del agente. Nunca viaja al servidor ni lo ve el widget.
- La clave privada no sale del token.
- Quien habla con el agente es el **widget** (en el navegador del usuario), que hace de puente con el servidor.

## Flujo

1. El widget pide al agente `GET /certificates` y el usuario elige un certificado.
2. El widget envía el certificado elegido al servidor: `POST /api/v1/signature-requests/{id}/prepare` con `{"certificate_pem": "<PEM>"}`.
3. El servidor valida el certificado (cadena, vigencia, revocación, CUIL) y, si es válido, responde con los desafíos: `challenge_id`, `document_name`, `hash_algorithm: "SHA-256"` y `hash_to_sign` (base64 de 32 bytes). Si no es válido responde `403`/`422` con `code` **antes de que se pida el PIN**.
4. El widget envía al agente `POST /sign` con los hashes y los nombres de los documentos. El agente muestra el diálogo de PIN con el nombre del titular del certificado (los nombres de los documentos quedan en su registro de actividad), pide el PIN **una vez** y firma.
5. El widget reenvía las firmas al servidor: `POST /api/v1/signature-requests/{id}/complete` con `{"signatures": [{"challenge_id", "signature_base64"}]}`.

## Formato de la firma

- `hash_to_sign`: base64 de los 32 bytes del SHA-256 de los atributos firmados del PDF.
- `signature_base64`: base64 de la firma **RSA PKCS#1 v1.5 sobre la estructura `DigestInfo`** de SHA-256 del hash.
  - `DigestInfo = 3031300d060960864801650304020105000420 || hash` (19 bytes de prefijo + 32 de hash).
  - En PKCS#11 corresponde al mecanismo **`CKM_RSA_PKCS`** con el `DigestInfo` armado por el agente (el token aplica el relleno `00 01 FF… 00`).
  - Longitud de la firma = longitud del módulo RSA (256 bytes para RSA 2048).
- Solo se admiten claves **RSA de 2048 bits o más**. ECDSA no está soportado todavía.

## Certificado enviado a `prepare`

- PEM del certificado del firmante (no la cadena, no la clave). La cadena se completa en el servidor con las anclas de `backend/trust/`.
- El CUIL se extrae del `serialNumber` del sujeto con formato `CUIL 20123456789` y se registra con la firma. Solo con `FIRMADOC_REQUIRE_CUIL_MATCH=true` debe coincidir con el del firmante de la solicitud; por defecto el único factor que se exige es el PIN del token.

## Errores que el servidor devuelve

| HTTP | `code` | Cuándo |
|---|---|---|
| 403 | `cuil_mismatch` | solo con `FIRMADOC_REQUIRE_CUIL_MATCH=true`: el CUIL del certificado no es el del firmante, o no tiene CUIL |
| 422 | `certificate_untrusted` | la cadena no llega a un ancla conocida |
| 422 | `certificate_expired` | certificado vencido |
| 422 | `certificate_revoked` | certificado revocado |
| 422 | `certificate_invalid` | falta el certificado, no vigente aún, uso de clave inadecuado, clave débil o no RSA, o revocación no verificable en `hard-fail` |
| 409 | — | el desafío venció, ya fue usado o no pertenece a la sesión |
| 422 | — | la firma no verifica contra el hash o contra la clave del certificado |

El agente no interpreta estos códigos: los muestra el widget.

## API HTTP del agente

El widget habla con el agente por HTTP en `http://127.0.0.1:{puerto}` (puerto 47123 por defecto, configurable). Solo existen **dos operaciones**; cualquier otra ruta responde `404` y otro método `405`. Implementación: `agent/src/firmadoc_agent/server.py`; pruebas: `agent/tests/test_agent_server.py`.

### Controles de acceso

- El agente escucha **solo** en `127.0.0.1`.
- Todo pedido debe llevar la cabecera `Origin` con un origen de la lista `allowed_origins` del agente (coincidencia **exacta** de esquema, host y puerto; sin comodines). Sin `Origin`, con `null` o con un origen ajeno: `403 origin_not_allowed`, sin tocar el token ni mostrar diálogos y sin cabeceras CORS.
- La cabecera `Host` debe ser `127.0.0.1:{puerto}` o `localhost:{puerto}`; otro valor (DNS rebinding): `403 host_not_allowed`.
- Las respuestas incluyen `Access-Control-Allow-Origin` con el **origen exacto** del pedido (nunca `*`), también las de error, para que el widget pueda leerlas. Además `Vary: Origin`, `Cache-Control: no-store` y `X-Firmadoc-Agent: <versión>`.
- La preflight `OPTIONS` (de ambas rutas) responde `204` para los orígenes permitidos, con `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers: Content-Type`, `Access-Control-Max-Age: 600` y, si el navegador envía `Access-Control-Request-Private-Network: true` (Chrome/Edge 142+), `Access-Control-Allow-Private-Network: true`.

### `GET /certificates`

Lista los certificados públicos de **usuario** de los tokens conectados (omite los de AC). No pide el PIN.

```json
{
  "agent_version": "0.1.0",
  "certificates": [
    {
      "id": "0123456789abcdef:01",
      "token_label": "Token del funcionario",
      "subject": "CN=Juan Pérez,2.5.4.5=CUIL 20123456789,C=AR",
      "issuer": "CN=AC de ...",
      "serial_number": "123456789",
      "not_before": "2026-01-01T00:00:00+00:00",
      "not_after": "2028-01-01T00:00:00+00:00",
      "certificate_pem": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n"
    }
  ]
}
```

`id` es opaco para el widget (internamente `<serie del token>:<CKA_ID en hex>`): se reenvía tal cual a `/sign`. `certificate_pem` es lo que se envía a `prepare` del servidor.

### `POST /sign`

`Content-Type: application/json` obligatorio (`415` si no). Cuerpo ≤ 1 MiB (`413 payload_too_large`) y ≤ 100 elementos (`413 too_many_items`).

```json
{
  "certificate_id": "0123456789abcdef:01",
  "items": [
    {
      "challenge_id": "c9e1a7b4-...",
      "document_name": "resolucion-0457.pdf",
      "hash_algorithm": "SHA-256",
      "hash_to_sign": "q1w2e3r4t5y6...=="
    }
  ]
}
```

El agente muestra **una** confirmación con todos los `document_name` y el sujeto del certificado, pide el PIN **una sola vez**, abre una sola sesión, firma todos los hashes y la cierra. Respuesta `200`:

```json
{ "signatures": [ { "challenge_id": "c9e1a7b4-...", "signature_base64": "MIIB...==" } ] }
```

Las firmas vuelven en el mismo orden y con el mismo `challenge_id`; el widget las envía a `complete`. **Nunca hay firmas parciales**: si falla una, falla el pedido entero.

### Errores del agente

Cuerpo `{"code": "...", "detail": "..."}` con `code` estable:

| HTTP | `code` | Cuándo |
|---|---|---|
| 400 | `invalid_request` | cuerpo malformado, falta un campo, `hash_algorithm` distinto de `SHA-256` o hash que no mide 32 bytes |
| 403 | `origin_not_allowed` / `host_not_allowed` | origen o `Host` no permitidos |
| 404 | `not_found` / `token_not_found` / `certificate_not_found` / `private_key_not_found` | ruta inexistente, sin token, certificado o clave privada no presentes |
| 405 | `method_not_allowed` | método no permitido para la ruta |
| 409 | `user_cancelled` | el usuario canceló o no respondió en 120 s (no se hizo ningún login) |
| 401 | `pin_incorrect` | PIN incorrecto: **un único intento**, el agente no reintenta; reintentar es decisión de la persona |
| 401 | `pin_expired` | el PIN del token expiró |
| 423 | `pin_locked` | el token tiene el PIN bloqueado |
| 429 | `busy` | ya hay una firma esperando confirmación (una a la vez) |
| 500 | `pkcs11_unavailable` / `pkcs11_error` | la biblioteca PKCS#11 no carga o el token falló |

Si queda un único intento antes del bloqueo, el diálogo lo advierte antes de pedir el PIN.

## Requisitos del agente real

- Escuchar solo en `127.0.0.1` y aceptar únicamente pedidos de los orígenes permitidos (**cumplido**, `agent-local-api`).
- Un único ingreso de PIN por lote, sin reintentos automáticos (**cumplido**, `agent-token-signing`).
- Confirmar con el usuario antes de pedir el PIN, en una ventana que muestra solo el nombre del titular y el campo de PIN; los documentos se ven en el widget y quedan en el registro del agente (**cumplido**, FIRDOC-51).
- Probado con SoftHSM (código PKCS#11) y de punta a punta contra el servidor con una PKI de prueba. Con el token físico de referencia (octubre de 2026): la biblioteca del fabricante carga y `diagnose` lista el certificado de la AC ONTI con el CUIL en el formato esperado. **Pendiente:** confirmar con ese token, con el PIN del titular, que acepta `CKM_RSA_PKCS` con `DigestInfo` (procedimiento en `agent/README.md`).
