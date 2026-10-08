# Firma en lote

Un lote agrupa N documentos de un mismo firmante y proveedor para firmarlos con una sola confirmación y,
con el proveedor `token`, un solo PIN (el agente firma los N hashes en una llamada). Cada documento conserva su
solicitud, su desafío de un solo uso, su versión inmutable, su auditoría y su webhook.

Todas las rutas usan la cabecera `X-API-Key`.

| Paso | Ruta |
|---|---|
| Crear | `POST /api/v1/signature-batches` |
| Preparar | `POST /api/v1/signature-batches/{id}/prepare` |
| Completar | `POST /api/v1/signature-batches/{id}/complete` |
| Consultar | `GET /api/v1/signature-batches/{id}` |

## Crear

```json
{"documents": [{"document_base64": "…", "external_document_id": "EXP-1"}, {"document_id": "…"}],
 "signer": {"full_name": "Juan Pérez", "identifier": "20123456789", "email": "jperez@example.org"},
 "provider": "token", "allowed_providers": ["token", "local"],
 "callback_url": "https://gestor.example.org/hooks/firmadoc"}
```

De 1 a `FIRMADOC_MAX_BATCH_SIZE` (50) documentos. Es atómico: si uno es inválido no se crea nada (`422`).

## Preparar y completar (proveedor `token`)

1. `prepare` con `{"certificate_pem": "…"}` devuelve un desafío por documento
   (`challenges[].signature_request_id`, `challenge_id`, `hash_to_sign`).
2. El agente local firma todos los hashes con un solo PIN (`POST /sign`, ver `agent-contract.md`).
3. `complete` con `{"signatures": [{"challenge_id": "…", "signature_base64": "…"}, …]}`.

Con `local`, `complete` no necesita firmas.

## Resultado y fallos parciales

`complete` responde `200` con el estado del lote y el de cada documento (`status`, `version_number`,
`download_url`, `error`). Un documento que falla no impide los demás:

| Estado del lote | Significado |
|---|---|
| `pending` / `signing` | sin preparar / preparado |
| `completed` | todos firmados |
| `partial_failure` | algunos firmados y otros no |
| `failed` | todos fallaron |

Un documento sin firma enviada queda en `signing` y puede completarse después con otra llamada a `complete`.
Los PDF firmados no viajan en la respuesta: descargarlos con `download_url`.
Para reintentar los fallidos, crear otro lote con sus `document_id`.

## Firmar el lote desde el widget

La respuesta de creación incluye `signing_url` (`{public_base_url}/sign/batch/{id}#t=<token>`), igual que en una
solicitud individual: se abre en un iframe o con el Web Component (ver `widget/README.md`). El widget de lote:

1. lista los documentos (nombre, páginas y tamaño) y deja elegir el método entre los de `allowed_providers`
   (sin ellos, solo el de `provider`). **La firma remota (`firmar`) no se admite en lotes**: crear un lote con ella
   responde `422`, y la tarjeta se muestra deshabilitada en el widget;
2. con `token`, elige y valida **un** certificado y pide **un** PIN: el agente firma los N hashes en una llamada;
3. muestra «N de M documentos firmados» con el estado de cada uno, ofrece **Descargar firmados** (un ZIP con los PDF
   vigentes de los firmados) y **Reintentar** (crea otro lote solo con los fallidos y lo abre; los firmados no se
   vuelven a firmar);
4. avisa al anfitrión con el mensaje `firmadoc:batch-completed` (sin PDF, firmas ni token).

El token del enlace sirve únicamente para ese lote (no abre solicitudes ni otros lotes) y no sustituye a la API key.
Endpoints del widget (`/api/v1/widget/batches/{id}`, con `Authorization: Bearer <token>`): `GET`, `POST /provider`,
`POST /prepare`, `POST /complete`, `GET /download` (ZIP) y `POST /retry`.

Límite conocido: el motivo del error de cada documento se muestra con la respuesta de `complete`; si se recarga la
página el documento figura como fallido sin detalle. El ZIP se arma en el servidor (archivo temporal): el tamaño
máximo es `FIRMADOC_MAX_BATCH_SIZE × FIRMADOC_MAX_DOCUMENT_BYTES`.
