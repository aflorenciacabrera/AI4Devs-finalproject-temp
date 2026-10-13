## 1. Página de autorización del simulado

- [x] 1.1 `mock_firmar.py`: extraer `_approve(operation, otp, pin, settings)` y `_reject(operation, settings)` de las rutas `approve`/`reject` (mismos códigos y estados); `GET /mock/firmar/authorize/{id}` con la página HTML (formulario OTP/PIN, «Firmar», «Rechazar», códigos visibles, «simulado»), `POST` con el formulario (`parse_qs`, `run_in_threadpool`), estados no pendientes, `404` si no existe; valores escapados.
- [x] 1.2 `tests/test_firmar.py`: formulario `200`, aprobación por formulario → `signed`, error y bloqueo al tercer intento sin callback, rechazo → `failed`/`remote_rejected`, inexistente → `404`, simulado apagado → `404`.

- [x] 1.3 Sandbox del iframe con `allow-popups allow-popups-to-escape-sandbox` en `widgetElement.ts`, `host.js`, `admin.js`, `widget-dialog.ts`, sus pruebas unitarias, `widget/README.md` y `README.md`; `tests/e2e/test_provider_choice_e2e.py` abre la página del simulado desde el enlace y firma desde ahí.

## 2. Firma remota en la demo

- [x] 2.1 `demo.py`: `_load_or_create_secrets` completa `firmar_client_secret` y `firmar_callback_secret` (≥ 32) sin regenerar los existentes; `prepare` fija `FIRMADOC_FIRMAR_BASE_URL`, `FIRMADOC_FIRMAR_MOCK_ENABLED`, `FIRMADOC_FIRMAR_CLIENT_ID` y los secretos; `guide` explica el recorrido y los códigos.
- [x] 2.2 `tests/test_demo.py`: variables fijadas; secretos estables y completados sobre un `demo.json` anterior conservando el token de administración; guía con «Firma remota», `123456` y `1234`; firma remota de punta a punta desde el panel (`allowed_providers` con `firmar`, `authorization_url` del mismo servidor, `POST` del formulario, v2 firmada, `stored_blob`); el lote del panel sigue sin `firmar`.
- [x] 2.3 `pytest tests -q --ignore=tests/e2e` y `ruff check` en verde.

## 3. Documentación

- [x] 3.1 `docs/demo.md` (sección «Firma remota con el servicio simulado», tabla «Qué crea»), `docs/firmar.md` (página de autorización, demo, «Límites» sin la frase del widget), `README.md` (modo demostración y fila en «Flujos a probar»).

## 4. Verificación

- [x] 4.1 Con `python -m firmadoc.demo` arriba: en el panel la tarjeta «Firma remota» aparece habilitada; «Continuar en el servicio de firma» abre la página del simulado; con OTP `123456` y PIN `1234` el widget pasa a «Documento firmado» y la v2 figura en «Documentos». Verificado el 2026-10-13 en Chrome (headless) contra `python -m firmadoc.demo --port 8010`: tarjeta habilitada, página del simulado en pestaña nueva, «Documento firmado» en el widget y v2 «Firmado» (proveedor FirmAR) en «Documentos».
