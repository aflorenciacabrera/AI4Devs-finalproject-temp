## 1. Nombre único en el servidor

- [x] 1.1 `firmadoc/filenames.py`: `clean_filename`, `download_name`, `unique_name`, `content_disposition` (`filename` + `filename*`), `attachment_headers`; `signature_flow.document_name` delega en `download_name`.
- [x] 1.2 Descargas con ese nombre: `api/widget_routes.py`, `api/routes.py`, `api/admin_routes.py` + `services/admin.version_download`, y nombres del ZIP en `services/widget_batch.signed_zip` (duplicados con `-2`, `-3`).

- [x] 1.3 Panel Angular: `filenameFrom()` en `frontend/src/app/core/admin-api.ts` lee `filename*` (UTF-8) antes que `filename`; test en `admin-api.spec.ts`; `npm run build` del panel.
- [ ] 1.4 Widget: `download()` en `widget/src/api/serverClient.ts` lee `filename*` antes que `filename` (hoy toma el fallback ASCII: sin acentos). PENDIENTE hasta que la otra tarea en paralelo commitee sus cambios en ese archivo; después, `npm run build` del widget.

## 2. Tests

- [x] 2.1 `tests/test_filenames.py`: acentos/espacios/paréntesis, extensión única, id como respaldo, limpieza, numeración de repetidos, cabecera UTF-8 y latin-1, saneado.
- [x] 2.2 Ajustar `test_admin_views.py` (v1 y v2 con el mismo nombre, sin `-vN`), `test_batch_widget.py` y los e2e; agregar en `test_widget_endpoints.py` la descarga del widget con el nombre original (con acento) y en `test_batch_widget.py` el ZIP con nombres repetidos.
- [x] 2.3 `pytest tests -q --ignore=tests/e2e` y `ruff check` en verde.

## 3. Documentación

- [x] 3.1 `README.md` (descarga en la API y flujos a probar) y `docs/demo.md` si mencionan el nombre del archivo descargado.

## 4. Verificación

- [ ] 4.1 Reiniciar la demo, firmar un PDF con nombre con espacios y acento y descargarlo desde el panel: conserva el nombre (lo ejecuta la usuaria).
