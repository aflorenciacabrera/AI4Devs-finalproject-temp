# API de documentos: estado, firmantes y verificación

Todas las rutas usan `X-API-Key` y solo ven los documentos del propio integrador (otro integrador recibe `404`). Los PDF también pueden entrar desde el panel de administración (ver `docs/admin.md`, «Firmar documento»).

## Estado y plazo

`GET /api/v1/documents/{id}` → `signing_status`, `signature_deadline`, `deadline_passed`,
`current_version_number`, `download_url`.

`PATCH /api/v1/documents/{id}` con `{"signing_status": "pending_signature", "signature_deadline": "2026-12-01T12:00:00-03:00"}`:

- `signing_status` solo admite `draft` y `pending_signature` (`signed` lo fija únicamente la firma).
  Un documento `signed` puede volver a `pending_signature` (otra ronda de firmantes) pero no a `draft` (`409`).
- `signature_deadline` exige zona horaria y fecha futura; `null` lo borra.
- **El plazo es informativo**: Firmadoc no bloquea firmas por plazo vencido (el comportamiento debe acordarse
  con cada integrador). Usar `deadline_passed` para decidir.

## Firmantes

`GET /api/v1/documents/{id}/signatures` → una entrada por firma, en orden: `version_number`, `signer_name`,
`signer_identifier`, `signed_at`, `provider`, `certificate` (sujeto, emisor, serie).
Sale del registro de Firmadoc (base de datos).

## Verificación

`POST /api/v1/documents/{id}/verify` relee el PDF vigente y comprueba, sin depender de la base salvo por el hash:

- `hash_matches`: SHA-256 del binario guardado contra el registrado (detecta alteración del almacenamiento).
- `signatures[]`: por firma, `intact`, `valid`, `trusted` (cadena hasta las anclas de `FIRMADOC_TRUST_DIR` y
  el certificado del proveedor `local`), `modification_level` y `ok`.
- `valid`: verdadero solo si el hash coincide, hay al menos una firma y todas están `ok`.

No consulta revocación: una firma emitida mientras el certificado era válido sigue siendo válida si se revoca
después; la revocación se comprobó y registró al firmar. Una firma con certificado de una AC no configurada
figura `trusted: false`. Para contrastar con una herramienta independiente, ver los ejemplos con `openssl cms -verify`
en las pruebas (`tests/test_documents_api.py`).
