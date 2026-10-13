## Context

Ver `proposal.md`. Hoy `demo.prepare()` fija las variables del servidor en `os.environ` y `panel_upload._enabled_providers` arma la lista de métodos del panel con `get_provider` sobre (token, firmar, local): `firmar` entra solo si `firmar_base_url` está seteada. El servicio simulado (`mock_firmar.py`, montado en `/mock/firmar` con `FIRMADOC_FIRMAR_MOCK_ENABLED=true`) ya implementa OAuth, `operations`, `approve`, `reject` y el callback firmado con HMAC, pero no sirve nada en la `authorization_url` que devuelve. El widget, en `remote_waiting`, abre esa URL en otra pestaña y consulta el estado hasta que el callback resuelva la solicitud. En la demo, backend y simulado corren en el mismo proceso `uvicorn`: las rutas sincrónicas van al threadpool, así que una llamada HTTP del servidor a sí mismo (prepare → simulado, y approve → callback) no bloquea el bucle de eventos.

## Goals / Non-Goals

**Goals:** la demo ofrece los tres métodos sin que la persona configure nada; el flujo remoto se completa desde el navegador; nada cambia fuera de la demo.

**Non-Goals:** autenticación real del usuario en el simulado (OTP y PIN fijos son la «credencial»); estado persistente del simulado (sigue en memoria); dependencia nueva para formularios (`python-multipart` no está instalado y no hace falta).

## Decisions

1. **Secretos en `demo.json`.** `_load_or_create_secrets` pasa a completar las claves que falten (`firmar_client_secret`, `firmar_callback_secret`) sin regenerar las existentes, para que un entorno anterior conserve su token de administración. Un secreto corto (< 32) se regenera, como ya pasa con los otros dos. Alternativa descartada: derivarlos del `signing_secret` (mezclaría secretos con fines distintos).
2. **Variables.** `FIRMADOC_FIRMAR_BASE_URL = {public_base_url}/mock/firmar`, `FIRMADOC_FIRMAR_MOCK_ENABLED=true`, `FIRMADOC_FIRMAR_CLIENT_ID=firmadoc`, secretos de `demo.json`, `FIRMADOC_FIRMAR_TIMEOUT_SECONDS` por defecto. `public_base_url` es `http://localhost:{puerto}`, así que el simulado queda en el mismo servidor y la `authorization_url` que devuelve (armada con `public_base_url`) abre en el navegador.
3. **Página de autorización en el simulado.** `GET /mock/firmar/authorize/{id}` devuelve HTML (formulario `otp`, `pin`, botones «Firmar» y «Rechazar»); `POST` a la misma ruta recibe el formulario `application/x-www-form-urlencoded`, parseado con `urllib.parse.parse_qs` (como ya hace `/oauth/token`), y responde la misma página con el resultado. Se extraen `_approve(operation, otp, pin, settings)` y `_reject(operation, settings)` para que la API y la página compartan la lógica (intentos, bloqueo, firma, callback). La página no exige el bearer: en el servicio real el usuario se autentica allí; en el simulado la credencial es el OTP y el PIN. Sin estado (`locked`, `signed`, `rejected`) la página lo informa y no vuelve a ofrecer el formulario. Operación inexistente: `404` HTML. Los valores que se muestran pasan por `html.escape`. El handler es `async` (lee el cuerpo) y delega la firma y el callback a `run_in_threadpool`.
4. **Códigos fijos y visibles.** La página muestra que el OTP es `123456` y el PIN `1234`: es un simulador y el objetivo es recorrer el flujo, no adivinarlos. La guía de la demo los repite.
5. **Orden de los métodos.** `PROVIDER_ORDER` no cambia (token, firmar, local): el proveedor inicial de la solicitud del panel sigue siendo `token`, y el widget conserva su preferencia actual.
6. **Pruebas.** En `tests/test_firmar.py` con el fixture existente: página `200` con el formulario, aprobación por formulario → callback → solicitud `signed`, OTP incorrecto → mensaje y, al tercer intento, bloqueo, rechazo → `failed`/`remote_rejected`, operación inexistente → `404`, simulado apagado → `404`. En `tests/test_demo.py`: variables y secretos estables (y completados en un `demo.json` anterior), guía, y firma remota de punta a punta desde el panel de la demo (`allowed_providers` incluye `firmar`, `prepare` devuelve la `authorization_url` del mismo servidor, `POST` del formulario, v2 firmada por la AC del simulado) con `firmar.TRANSPORT` apuntando al `TestClient`, como en `test_firmar.py`.

7. **Sandbox del iframe con `allow-popups allow-popups-to-escape-sandbox`.** Al verificar en Chrome, el enlace `target="_blank"` de `remote_waiting` no abría nada: el `sandbox` de todos los embebidos bloquea las ventanas nuevas. Se agregan las dos banderas en los cuatro lugares que lo fijan y en las dos guías que lo documentan; `allow-popups-to-escape-sandbox` es necesaria para que la pestaña nueva no herede el aislamiento (sin ella, la página del servicio no podría enviar su formulario). Alternativa descartada: navegar la propia pestaña del widget al servicio (perdería la pantalla de espera y el `postMessage` a la página anfitriona).

## Risks / Trade-offs

- [El servidor se llama a sí mismo por HTTP en la demo] → las rutas involucradas son sincrónicas (threadpool) o delegan con `run_in_threadpool`; el timeout del cliente (10 s) evita un cuelgue indefinido. Se verifica a mano con la demo arriba.
- [La AC del simulado se genera en `data/demo/local-cert/firmar-mock/` en la primera aprobación] → `verification_anchors` ya la suma con el simulado habilitado; `--reset` la borra junto con el resto.
- [Un simulado habilitado por defecto podría confundirse con un servicio real] → la página y la guía dicen «simulado» en todas partes; `preflight` sigue marcándolo como problema en modo real y la demo no corre en modo real.
- [Otra sesión editando el repo] → `git status` antes de commitear y `git add` por rutas.

## Migration Plan

Sin migraciones. Un `data/demo/demo.json` anterior se completa solo. Rollback: revertir el commit; las claves extra en `demo.json` no molestan.
