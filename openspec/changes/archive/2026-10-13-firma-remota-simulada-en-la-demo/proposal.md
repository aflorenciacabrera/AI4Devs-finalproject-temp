## Why

En el panel de la demo (`python -m firmadoc.demo`) la tarjeta «Firma remota» no aparece entre los métodos de firma: el proveedor `firmar` solo se habilita con `FIRMADOC_FIRMAR_BASE_URL` y la demo no configura ninguna variable `FIRMADOC_FIRMAR_*`. Además, aunque se configurara a mano, el servicio simulado devuelve una `authorization_url` (`/mock/firmar/authorize/{id}`) que no existe como página: la aprobación con OTP y PIN solo se puede hacer por API con el token OAuth, así que nadie puede recorrer el flujo desde el widget. La demo es la forma en que se muestra Firmadoc y el README promete tres métodos. Implementa **FIRDOC-56** (épica FIRDOC-5) sobre la HU 7 del README (firma remota desde el mismo widget).

## What Changes

- La demo habilita el proveedor `firmar` contra el servicio simulado del mismo servidor: `FIRMADOC_FIRMAR_BASE_URL=http://localhost:<puerto>/mock/firmar`, `FIRMADOC_FIRMAR_MOCK_ENABLED=true`, y secretos de cliente y de callback generados una vez (32 caracteres o más) y guardados en `data/demo/demo.json` junto a los existentes. En entornos ya creados se agregan sin regenerar el token de administración ni el secreto del widget.
- El servicio simulado sirve la **página de autorización** en la `authorization_url` que ya devuelve: formulario con OTP y PIN, botón «Rechazar», mensajes de error, bloqueo tras 3 intentos y resultado final («volvé a Firmadoc»). Al aprobar firma el PDF y llama al callback de Firmadoc como hoy lo hace la ruta de API `approve`. La página no exige el token OAuth (es la pantalla del usuario en el servicio, no una ruta de la API del simulado).
- La guía de la demo explica el recorrido («Firma remota» → «Continuar en el servicio de firma» → OTP `123456` y PIN `1234`).
- **Corrección encontrada al verificar en Chrome:** el `sandbox` del iframe del widget (`allow-scripts allow-same-origin allow-downloads`) bloqueaba la apertura de pestañas, así que el enlace «Continuar en el servicio de firma» no abría nada en ningún embebido. Se agregan `allow-popups allow-popups-to-escape-sandbox` en el Web Component, el panel estático, el panel Angular, la página de ejemplo y la guía de integración, y la prueba en Chrome de la firma remota pasa ahora por la página del simulado.
- Documentación: `docs/demo.md`, `docs/firmar.md` (página de autorización; el widget ya ofrece el proveedor) y `README.md` (modo demostración y «Flujos a probar»).

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `demo-mode`: nuevo requisito «Firma remota con el servicio simulado» (variables, secretos estables, guía); el requisito «Guía al arrancar» menciona la firma remota.
- `firmar-mock-service`: nuevo requisito «Página de autorización del usuario» (`GET`/`POST …/authorize/{id}` sin token OAuth, OTP/PIN, rechazo, bloqueo); el requisito «Autenticación OAuth simulada» aclara que el token se exige en las rutas de la API, no en la página.
- `widget-embedding`: el requisito «Embebido por iframe» exige que el aislamiento aplicado y documentado permita abrir una pestaña nueva fuera del sandbox (enlace al servicio de firma remota).

## Impact

- `backend/src/firmadoc/demo.py` (`_load_or_create_secrets`, `prepare`, `guide`).
- `backend/src/firmadoc/mock_firmar.py` (aprobación y rechazo extraídos a funciones; página HTML y su `POST`).
- Sandbox del iframe: `widget/src/embed/widgetElement.ts`, `widget/examples/host.js`, `widget/README.md`, `backend/src/firmadoc/admin_ui/admin.js`, `frontend/src/app/sections/widget-dialog.ts`, `README.md` (y sus pruebas unitarias).
- Tests: `tests/test_firmar.py` (página de autorización), `tests/test_demo.py` (variables, secretos, guía y firma remota de punta a punta desde el panel de la demo), `tests/e2e/test_provider_choice_e2e.py` (en Chrome, el enlace abre la página del simulado y se firma desde ahí).
- Docs: `docs/demo.md`, `docs/firmar.md`, `README.md`.
- Sin cambios en la API de integradores ni en el esquema. Fuera de la demo, `firmar` sigue deshabilitado salvo configuración explícita.

## Fuera de alcance

- Firma remota en lotes (el servidor sigue sin admitirla; el panel sigue armando los lotes solo con `token` y `local`).
- Una opción para arrancar la demo sin firma remota: es demostración y el simulado no tiene efectos fuera del proceso.
- Parecerse visualmente al servicio real ni verificar el contrato del servicio real (sigue simulado, `docs/firmar.md`).
- Modo real: la demo sigue negándose con `FIRMADOC_REAL_MODE=true`, y el preflight sigue marcando el simulado como problema en ese modo.
