## Why

El análisis sobre el `<iframe>` y el permiso de acceso a la red local (Chrome/Edge 142+) cerró con tres recomendaciones: iframe como modo principal con `allow="local-network-access"`, ventana emergente como modo alternativo documentado, y probar en Chrome y Edge antes de la Entrega 2 (Firefox y Safari sin verificar). La primera ya está aplicada en todos los embebidos; la segunda figura en el README como «no implementada, a evaluar», y la tercera no tiene forma de ejecutarse: la suite en navegador real solo sabe lanzar Chrome. La usuaria pidió aplicar la recomendación. Implementa **FIRDOC-57** (épica FIRDOC-5), sobre la HU 2 del README (integración del widget en sistemas anfitriones).

## What Changes

- **Ventana emergente como modo alternativo, implementado.** Cuando el widget corre en su propia ventana abierta con `window.open` desde la página anfitriona, avisa a `window.opener` con los mismos mensajes y el mismo `targetOrigin` explícito por cada origen permitido (nunca `"*"`); embebido en un iframe sigue avisando a `window.parent`. Al pulsar «Cerrar» en una ventana propia, el widget la cierra después de avisar. Sin anfitrión (pestaña abierta a mano) no envía nada ni cierra nada, como hasta ahora.
- **Página anfitriona de ejemplo con `mode=popup`:** un botón abre la `signing_url` en una ventana emergente (gesto del usuario, para que no la bloquee el navegador), valida los mensajes por ventana y origen, y registra `firmadoc:closed` cuando la ventana se cierra.
- **Guías:** README (sección 1.2: la alternativa pasa de «no implementada» a «Opción 3», con sus costos) y `widget/README.md` (snippet, variante Angular, cuándo elegirla: el permiso de red local se pide al origen de Firmadoc, sin delegación por `allow`, y no depende de que el anfitrión conserve el atributo).
- **El panel Angular abre el widget en una ventana propia** en lugar del diálogo (pedido de la usuaria durante el cambio: evitar un módulo dentro de otro modal y mejorar la visual). La ventana se reserva en el clic de «Cargar y firmar», antes de leer y subir el PDF, para que el navegador no la bloquee; si igual la bloquea, el diálogo con el iframe queda como respaldo. La tarjeta ofrece «Ir a la ventana de firma» mientras está abierta y avisa si se cierra sin firmar. Es el ejemplo de referencia del modo para integradores Angular.
- **Prueba en Chrome y Edge:** la suite en navegador real acepta `FIRMADOC_E2E_BROWSER` (`chrome` por defecto, `msedge` para Edge) y se documenta cómo correrla en ambos; nueva prueba del modo ventana emergente. Firefox y Safari quedan explícitamente como no verificados.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `angular-panel`: «Carga de documentos y widget embebido en Angular» abre el widget en una ventana propia, con el diálogo como respaldo si el navegador la bloquea.
- `widget-embedding`: nuevo requisito «Ventana emergente como modo alternativo»; «Mensajes hacia la página anfitriona» admite `window.opener` como destinatario; «Página anfitriona de ejemplo» incluye el modo ventana emergente; «Guía de integración con Angular» documenta la alternativa; «Prueba de punta a punta en un navegador real» se puede ejecutar en Chrome o en Edge y cubre la ventana emergente.

## Impact

- `widget/src/embed/hostMessages.ts` (destinatario: `parent` o `opener`; cierre de la ventana propia), `widget/src/main.tsx` si hace falta pasar el cierre.
- `widget/examples/host.js` y `host.html` (`mode=popup`).
- Panel Angular: `frontend/src/app/sections/widget-window.ts` (nuevo), `sign.ts`, `sign.html`, sus pruebas y `frontend/README.md`; `widget-dialog.ts` queda como respaldo.
- `widget/README.md`, `README.md` (1.2, «Flujos a probar» y supuesto 7).
- `tests/e2e/conftest.py` (`FIRMADOC_E2E_BROWSER`), `tests/e2e/test_widget_e2e.py` (ventana emergente), `widget/tests/embed.test.ts` (opener).
- Sin cambios en el servidor, la API, el panel ni el esquema.

## Fuera de alcance

- Cambiar el modo principal: el iframe sigue siendo el recomendado y el que usan los paneles de Firmadoc.
- Verificar Firefox y Safari (no están instalados en el entorno de prueba; queda como supuesto).
- Que el Web Component ofrezca el modo ventana emergente (es un envoltorio del iframe; la ventana la abre el anfitrión con una línea).
