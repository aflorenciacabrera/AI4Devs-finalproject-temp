## Why

Al elegir «Firma remota», el botón «Continuar en el servicio de firma» abre la página de autorización del servicio en otra pestaña y la persona queda fuera del panel; al volver, el widget ya cambió solo. La usuaria pidió que sea una ventana emergente chica sobre el panel, no otra pantalla. Implementa **FIRDOC-59** (épica FIRDOC-5), sobre la HU 7 del README (firma remota desde el mismo widget).

## What Changes

- El enlace del widget abre el servicio con `window.open` en una ventana emergente acotada y centrada sobre la del panel. Si el navegador la bloquea, el enlace sigue su curso y abre una pestaña, como hasta ahora. Un segundo clic reemplaza la ventana anterior.
- Cuando la solicitud deja de estar en espera (firmada, rechazada, vencida o cancelada), el widget cierra esa ventana si sigue abierta.
- La página del servicio simulado, al terminar, avisa que la ventana se cierra sola (y que se puede cerrar a mano si no).
- La cabecera del diálogo del panel Angular dice «Firma de documento» (o «Firma de documentos» en un lote) en lugar del nombre del PDF, que ya figura en la tarjeta (pedido de la usuaria durante el cambio).
- Documentación (`docs/demo.md`, `widget/README.md`, `README.md`) y pruebas.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `widget-provider-choice`: «Firma remota desde el widget» abre el servicio en una ventana emergente (pestaña si la bloquean) y la cierra al terminar.
- `widget-embedding`: el escenario «Enlace al servicio de firma remota» de «Embebido por iframe» habla de ventana emergente.

## Impact

- `widget/src/screens/RemoteWaiting.tsx`, `widget/tests/choice.test.tsx`, `tests/e2e/test_provider_choice_e2e.py`.
- `backend/src/firmadoc/mock_firmar.py` (textos del resultado).
- Docs: `docs/demo.md`, `widget/README.md`, `README.md`.
- Sin cambios en la API ni en el contrato con el servicio.

## Fuera de alcance

- Cerrar la ventana desde la propia página del servicio (requeriría script en línea en el simulado y no aplica al servicio real).
- Embeber el servicio dentro del widget (es otro origen y la autorización debe ocurrir en su propia ventana).
