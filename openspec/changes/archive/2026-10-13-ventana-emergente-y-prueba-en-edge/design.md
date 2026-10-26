## Context

Ver `proposal.md`. `createHostNotifier(allowedOrigins, requestId, parent)` elige hoy el destinatario con `window.parent !== window ? window.parent : null`: en una ventana propia no hay destinatario y los mensajes se descartan. La página del widget tiene `frame-ancestors <allowed_origins>` (solo aplica a marcos) y el token de la solicitud va en el fragmento de la URL, así que abrirla como ventana principal no cambia nada del lado del servidor. La suite en Chrome (`tests/e2e/`) lanza `p.chromium.launch(channel="chrome")`; Playwright también sabe lanzar Edge con `channel="msedge"`, instalado en Windows 11.

## Goals / Non-Goals

**Goals:** mismo contrato de mensajes en los dos modos; cero cambios en el servidor; la prueba en navegador real corre en Chrome y en Edge sin tocar el código de las pruebas.

**Non-Goals:** mensajes entrantes (siguen prohibidos); un «modo» en el Web Component; soportar `noopener` (sin `opener` no hay forma de avisar: el integrador consulta el resultado con su API key, como siempre).

## Decisions

1. **Destinatario: `parent` si está enmarcado, si no `opener`.** `window.parent !== window` gana sobre `window.opener` (un iframe puede tener `opener` heredado). `opener` puede ser `null` (pestaña abierta a mano o `noopener`) o estar cerrado: se comprueba `closed` antes de cada envío y se descarta en silencio. El `targetOrigin` sigue siendo cada origen de `allowed_origins`: si el anfitrión que abrió la ventana no es uno de ellos, el navegador no entrega nada. Alternativa descartada: `postMessage` a `"*"` con `opener` (expondría el estado de la firma a cualquier página que abra la URL).
2. **Cierre de la ventana propia.** `closed()` envía el mensaje y, si el destinatario es `opener` (no `parent`), llama a `window.close()`; el navegador lo permite porque la ventana la abrió un script. En iframe no se cierra nada (no hay ventana propia). Se inyecta como función (`closeWindow`) para probarlo sin DOM real.
3. **Página de ejemplo: `mode=popup` con botón.** `window.open` fuera de un gesto del usuario lo bloquean todos los navegadores; la prueba hace clic en el botón. La página valida `event.source === popup && event.origin === widgetOrigin`, registra los mensajes en `window.__messages` como los otros modos y, con un temporizador sobre `popup.closed`, registra el cierre para que la prueba lo compruebe.
4. **`FIRMADOC_E2E_BROWSER`.** El fixture `browser` lee la variable (`chrome` por defecto; `msedge`); un valor desconocido falla con un mensaje claro. Las pruebas no saben en qué navegador corren. Se documenta en el README y en `tests/e2e`.
5. **Prueba de la ventana emergente.** Con el proveedor `local` (no necesita agente): la página anfitriona abre la ventana, `context.expect_page()` la captura, se firma, la página recibe `firmadoc:signed`, «Cerrar» cierra la ventana y llega `firmadoc:closed`. Más una prueba unitaria de `createHostNotifier` con un `opener` falso (envío por origen, `closed`, cierre).

## Risks / Trade-offs

- [Bloqueadores de ventanas emergentes] → la guía exige abrirla en un gesto del usuario y muestra cómo detectar `window.open` devolviendo `null`.
- [La persona cierra la ventana sin terminar] → el anfitrión lo detecta con `popup.closed`; el estado confiable sigue siendo el del backend (`GET /api/v1/signature-requests/{id}`), como en el iframe.
- [Edge y Chrome comparten motor] → la prueba en Edge verifica la instalación y las políticas reales del navegador, no un motor distinto; Firefox y Safari siguen sin verificar y así se documenta.

## Migration Plan

Sin migraciones ni cambios de API. Rollback: revertir el commit.
