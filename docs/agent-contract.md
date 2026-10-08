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
4. El widget envía al agente `POST /sign` con los hashes y los nombres de los documentos. El agente muestra el diálogo de confirmación con el nombre del documento, pide el PIN **una vez** y firma.
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
- El CUIL debe estar en el `serialNumber` del sujeto con formato `CUIL 20123456789` y coincidir con el del firmante de la solicitud.

## Errores que el servidor devuelve

| HTTP | `code` | Cuándo |
|---|---|---|
| 403 | `cuil_mismatch` | el CUIL del certificado no es el del firmante, o no tiene CUIL |
| 422 | `certificate_untrusted` | la cadena no llega a un ancla conocida |
| 422 | `certificate_expired` | certificado vencido |
| 422 | `certificate_revoked` | certificado revocado |
| 422 | `certificate_invalid` | falta el certificado, no vigente aún, uso de clave inadecuado, clave débil o no RSA, o revocación no verificable en `hard-fail` |
| 409 | — | el desafío venció, ya fue usado o no pertenece a la sesión |
| 422 | — | la firma no verifica contra el hash o contra la clave del certificado |

El agente no interpreta estos códigos: los muestra el widget.

## Requisitos para el agente real (change `agente-local`)

- Escuchar solo en `127.0.0.1` y aceptar únicamente pedidos de los orígenes permitidos del integrador.
- Un único ingreso de PIN por lote, sin reintentos automáticos (un PIN erróneo cuenta contra el límite de bloqueo del token).
- Confirmar con el usuario, mostrando el nombre del documento, antes de pedir el PIN.
- Probar con SoftHSM y confirmar con un token físico que acepta `CKM_RSA_PKCS` con `DigestInfo`.
