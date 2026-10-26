## Context

El esquema (change archivado `scaffolding-y-esquema-bd`) ya contiene `Document`, `DocumentVersion`, `SignatureRequest`, `SigningChallenge` y `AuditEvent`, con las garantías de inmutabilidad en la base. Este change agrega la API y el motor PAdES. El contrato de los endpoints está en el README (sección 4); el proveedor `token` reutilizará exactamente el mismo flujo, por lo que el diseño debe separar "qué se firma y cómo se incrusta" (compartido) de "quién produce la firma" (por proveedor).

## Goals / Non-Goals

**Goals:**
- Flujo `create` → `prepare` → `complete` completo con el proveedor `local`, con firma PAdES B-B verificable.
- Interfaz de proveedor que el proveedor `token` pueda implementar sin tocar el flujo.
- Atomicidad: o se crea la versión firmada y se consume el desafío, o no cambia nada.

**Non-Goals:**
- Validación de cadena/revocación/CUIL de certificados de terceros, sello de tiempo, webhooks, lotes (ver "Fuera de alcance" del proposal).

## Decisions

1. **Firma interrumpida de pyHanko.** `prepare` usa `PdfSigner.digest_doc_for_signing` para reservar el espacio de firma y obtener los atributos firmados; el hash a firmar es el SHA-256 de esos atributos. `complete` arma el CMS con la firma recibida y llama a `PdfTBSDocument.finish_signing`. Alternativa descartada: firmar el PDF completo en un solo paso, que no sirve para el token (la clave no sale del dispositivo). **Se valida primero con un spike** (tarea 1) porque la API exacta de pyHanko condiciona el resto.
2. **Estado intermedio entre `prepare` y `complete`.** El PDF con el espacio reservado y los atributos firmados se guardan en el almacenamiento bajo `prepared/{challenge_id}/` (no son `DocumentVersion`: no son documentos válidos). Se descartan al completar o al vencer. Alternativa descartada: recalcular en `complete`, que no es determinista (el atributo de hora cambia el hash).
3. **Interfaz `SignatureProvider` (Protocol)** con `prepare(request, document_bytes, ctx) -> PreparedSignature` y `produce_signature(prepared, signatures) -> bytes`. El servicio de flujo (compartido) hace el trabajo de PDF; el proveedor solo aporta el certificado y la firma del hash. `LocalPAdESProvider` firma con la clave propia; `token` (futuro) recibirá las firmas del agente.
4. **Certificado de demostración.** Un único certificado RSA 2048 autofirmado ("Firmadoc Demo Signer"), generado en el primer uso con `cryptography` en `FIRMADOC_LOCAL_CERT_DIR` (clave `.key` con permisos restringidos, fuera de git), registrado en `Certificate` con `provider: local`. El nombre y el CUIL del firmante real se dejan en el motivo/nombre de la firma (`reason`), no en el certificado. No se valida CUIL para `local`: esa verificación aplica a certificados de terceros (token).
5. **Sesión del firmante (`session_ref`).** Se toma de la cabecera opcional `X-Session-Ref`; si falta, se usa `request:{id}`. `complete` rechaza (`409`) desafíos de otro `session_ref`. El widget futuro enviará un valor ligado a la `signing_url`.
6. **Consumo atómico del desafío.** `UPDATE signing_challenge SET consumed_at=now WHERE id=? AND consumed_at IS NULL AND expires_at>now` y se verifica `rowcount == 1`; si no, `409`. Esto aprovecha el trigger de un solo uso y evita carreras entre dos `complete` simultáneos.
7. **Orden de escritura en `complete`.** (a) verificar firma contra el hash; (b) consumir desafío; (c) escribir el binario en el almacenamiento con nombre `documents/{document_id}/v{n}-{version_id}.pdf` (inmutable; el id de la versión evita que un binario huérfano de una transacción fallida bloquee el reintento); (d) en la misma transacción insertar `DocumentVersion`, actualizar `current_version_id`, `signing_status` y estado de la solicitud, y registrar `signed`. Si falla la transacción, el archivo huérfano es inofensivo. Los fallos de verificación marcan la solicitud `failed` y registran `failed`.
8. **Almacenamiento detrás de un Protocol** (`DocumentStorage`: `save`, `read`) con `LocalFileStorage` en `FIRMADOC_STORAGE_DIR`; resuelve rutas con `Path.resolve()` y rechaza las que salen del directorio. Permite cambiar a object storage sin tocar el flujo.
9. **Capas.** `api/` (routers FastAPI y schemas Pydantic), `services/signature_flow.py` (casos de uso), `providers/` (interfaz y `local`), `storage.py`, `auth.py` (dependencia `X-API-Key`). Los routers no contienen lógica de negocio.
10. **Autenticación.** Se hashea la clave recibida con SHA-256 y se busca por `api_key_hash` (índice único); el acceso a cada recurso se filtra por `integrating_system_id` y un recurso ajeno responde `404` (no `403`) para no revelar su existencia.
11. **Tamaño máximo** del PDF: `FIRMADOC_MAX_DOCUMENT_BYTES` (por defecto 20 MB), validado tras decodificar y antes de parsear. Se comprueba la cabecera `%PDF-` y que pyHanko pueda abrirlo.
12. **Verificación en tests con una herramienta distinta de la que firma.** La suite valida con `pyhanko.sign.validation` (ruta de código independiente de la de firma) y, si `openssl` está disponible, también verifica el CMS extraído; ese segundo chequeo se omite si falta. La verificación con una herramienta de terceros (p. ej. Adobe/`pdfsig`) queda como paso manual documentado.

## Risks / Trade-offs

- **API de pyHanko (alto):** la firma interrumpida es poco ejemplificada. Mitigación: spike previo a todo el resto y tests de integridad desde el principio.
- **Archivos intermedios** en `prepared/` pueden acumularse si el usuario abandona. Mitigación: limpieza al vencer el desafío (tarea de mantenimiento simple al preparar/completar); un job periódico queda para después.
- **Un solo certificado de demo compartido:** todas las firmas `local` comparten emisor; es aceptable para demostración y se documenta que es firma electrónica, no digital.
- **Fallo entre escribir el binario y confirmar la transacción:** deja un archivo huérfano; se tolera por diseño (decisión 7).
- **`signed_document_base64` en la respuesta** puede ser grande; es el contrato del README, se mantiene.

## Open Questions

- ¿Hash a firmar para el token: DigestInfo o hash crudo? Depende del mecanismo PKCS#11 elegido en el change del agente; no afecta a `local`.
- ¿Política de limpieza de `prepared/` y de solicitudes `signing` abandonadas? Se resuelve con el panel de administración.

## Resultado del spike (tarea 1.2)

Secuencia validada con pyHanko 0.37: `PdfSigner.async_digest_doc_for_signing` con un `ExternalSigner` (firma ficticia de relleno) → `signer.signed_attrs(document_digest, "sha256", use_pades=True)` → el hash a firmar es el SHA-256 del DER de esos atributos → `async_sign_prescribed_attributes` con un `ExternalSigner` que lleva la firma real → `PdfTBSDocument.async_finish_signing`. El estado entre pasos son cuatro valores (digest del documento, inicio y fin de la región reservada, atributos firmados en DER) más el PDF con el espacio reservado. La firma resultante valida con `pyhanko.sign.validation` y con `openssl cms -verify`.
