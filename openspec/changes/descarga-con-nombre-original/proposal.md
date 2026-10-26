## Why

Al descargar un PDF firmado, Firmadoc le cambiaba el nombre: `documento-firmado-v2.pdf` en el widget, `documento-v2.pdf` en la API de integración, `<nombre>-v2.pdf` en el panel y dentro del ZIP del lote, y además reemplazaba espacios, acentos y paréntesis por `_`. La usuaria pidió que el archivo descargado conserve el nombre original con el que se cargó. Implementa **FIRDOC-53** (épica FIRDOC-5); HU «Firmar con token USB desde el sistema web» (descarga del firmado) y HU6 «Firma en lote».

## What Changes

- El nombre de un documento (`external_document_id`, que el panel llena con el nombre del archivo cargado sin `.pdf`) se conserva tal cual: los separadores de ruta pasan a `_` y solo se quitan caracteres de control y comillas. Ese nombre con `.pdf` es el que se muestra en el widget, el que llega al agente y el del archivo descargado.
- Todas las descargas (widget, API de integración, panel de administración y cada PDF dentro del ZIP del lote) usan ese nombre, **sin sufijo de versión**. En el ZIP, dos documentos con el mismo nombre se distinguen con `-2`, `-3`… antes de la extensión.
- La cabecera `Content-Disposition` lleva `filename` (versión latin-1, para clientes simples) y `filename*` (UTF-8, RFC 6266) para que los acentos lleguen bien a cualquier navegador.
- Widget y panel Angular ya toman el nombre de la cabecera: no cambian.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `signature-requests`: nuevo requisito «Nombre de archivo en las descargas» (aplica a las descargas del widget, de la API y del panel, y a los nombres dentro del ZIP del lote).

## Impact

- Nuevo `backend/src/firmadoc/filenames.py` (`clean_filename`, `download_name`, `unique_name`, `content_disposition`, `attachment_headers`).
- `services/signature_flow.py` (`document_name`), `api/widget_routes.py`, `api/routes.py`, `api/admin_routes.py`, `services/admin.py`, `services/widget_batch.py`.
- Tests: `tests/test_filenames.py` (nuevo), ajustes en `test_admin_views.py`, `test_batch_widget.py`, `tests/e2e/test_batch_e2e.py`, `tests/e2e/test_panel_views_e2e.py`; prueba de la cabecera en `test_widget_endpoints.py`.
- Cambio visible para integradores: el nombre sugerido en `GET /documents/{id}/versions/{n}/download` deja de ser `documento-v{n}.pdf`.

## Fuera de alcance

- Guardar el nombre original en un campo propio del documento (hoy viaja en `external_document_id`).
- Cambiar el nombre del ZIP (`documentos-firmados.zip`).
