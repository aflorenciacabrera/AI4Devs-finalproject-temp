## Why

El integrador hoy solo puede crear solicitudes y descargar versiones. Le faltan tres cosas que ya figuran en el backlog: marcar un documento como pendiente de firma con una fecha límite (FIRDOC-25), saber quiénes lo firmaron (FIRDOC-25, FIRDOC-13) y comprobar por su cuenta que un PDF firmado sigue siendo íntegro y confiable (FIRDOC-26, FIRDOC-8). El modelo ya tiene `Document.signing_status` y `signature_deadline`, y cada firma ya queda registrada en `SignatureRequest` y `Certificate`, pero nada de eso se expone.

Backlog: FIRDOC-25 (HU9), FIRDOC-26 (HU10), y el endpoint `GET /documents/{id}/signatures` de FIRDOC-13.

## What Changes

- **Estado del documento** (`document-status`): `GET /api/v1/documents/{id}` devuelve el estado, la fecha límite, si venció y la versión vigente; `PATCH /api/v1/documents/{id}` cambia `signing_status` (`draft` ↔ `pending_signature`) y fija o borra `signature_deadline`.
- **Firmantes** (`document-verification`): `GET /api/v1/documents/{id}/signatures` lista, en orden, quién firmó (nombre, fecha, certificado, proveedor y versión resultante).
- **Verificación** (`document-verification`): `POST /api/v1/documents/{id}/verify` relee el PDF vigente y comprueba (a) que su hash coincide con el registrado, (b) para cada firma, integridad criptográfica, cadena hasta las anclas de confianza y que las firmas anteriores no fueron alteradas por las posteriores. Informa el resultado por firma y global. No hay migración: todo sale de datos ya guardados.

## Capabilities

### New Capabilities

- `document-status`: consulta y cambio del estado de firma y de la fecha límite.
- `document-verification`: listado de firmantes y verificación de integridad y confianza.

### Modified Capabilities

- Ninguna.

## Impact

- Servidor: `services/documents.py`, rutas y esquemas nuevos, y una función de verificación en `pdf_engine.py`. Sin migración.
- Documentación: `docs/documents-api.md`.

## Fuera de alcance

- **Comportamiento al vencer el plazo**: la fuente consultada no lo define y debe acordarse con cada integrador. Se expone `deadline_passed` para que el integrador decida; Firmadoc no bloquea ni cancela firmas por plazo vencido.
- Consulta de revocación al verificar (usa los datos de confianza locales; la revocación se comprueba al firmar y queda registrada).
- Verificación de sellos de tiempo (change de sello de tiempo).
- Listado de documentos con filtros (change del panel de administración).
