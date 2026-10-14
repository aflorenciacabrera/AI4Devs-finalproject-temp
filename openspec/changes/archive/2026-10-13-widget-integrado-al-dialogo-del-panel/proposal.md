## Why

Con FIRDOC-57 el panel Angular pasó a abrir el widget en una ventana propia. La usuaria la descartó: la dirección del widget queda visible en la barra del navegador y prefiere el diálogo integrado como opción más segura. Pero dentro del diálogo el widget se ve como «un modal dentro de otro modal»: dibuja su propio marco (barra «Firmadoc · Módulo embebido», borde, fondo y radio de tarjeta) y sus pantallas llevan aclaraciones de más (leyendas al pie, descripciones largas de los métodos, textos de espera). Implementa **FIRDOC-58** (épica FIRDOC-5), sobre la HU 2 del README.

## What Changes

- **El panel vuelve al diálogo** con el iframe como único modo: se retira del panel la ventana propia (`widget-window.ts`), `sign.ts` queda como antes de FIRDOC-57. La ventana emergente sigue como alternativa documentada para integradores, ahora con la advertencia de que la dirección del widget queda visible (el token del fragmento se borra de la URL y del historial antes de dibujar, pero la dirección y el identificador de la solicitud se ven).
- **El widget sin marco propio:** sin barra de marca, sin borde, fondo ni radio de tarjeta y sin franja de color por estado; el fondo del documento es transparente y los botones quedan al pie sobre una línea. Así se ve como parte del diálogo (o de la página) que lo contiene.
- **Tema claro u oscuro del anfitrión:** el widget acepta `?theme=light|dark` en la URL de firma (antes del fragmento) y, sin él, sigue el esquema del sistema. El panel se lo pasa según su propio tema. Colores oscuros nuevos en los tokens del widget.
- **Menos aclaraciones:** se quitan las leyendas al pie de «Elegí el método», «Firmar con el servicio de firma remota», «Esperando la firma en el servicio remoto», «El certificado no pudo validarse», «No detectamos Firmadoc Agent»; el aviso de demostración de «Firmar el documento» (el subtítulo ya lo dice); la frase introductoria y la nota de versiones de «Documento firmado»; los subtextos de los pasos de «Esperando tu confirmación». Las descripciones de los métodos se acortan a una línea (la de demostración sigue aclarando que no tiene presunción legal).

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `angular-panel`: «Carga de documentos y widget embebido en Angular» vuelve al diálogo con el iframe (sin ventana emergente) y pasa el tema al widget.
- `signing-widget`: nuevo requisito «Apariencia integrada en el anfitrión» (sin marco propio, tema por parámetro o sistema, sin aclaraciones redundantes).
- `widget-embedding`: «Ventana emergente como modo alternativo» advierte que la dirección queda visible y deja de citar al panel como usuario del modo.

## Impact

- Widget: `Screen.tsx`, `styles/app.css`, `styles/tokens.css`, `main.tsx` (tema), `messages/es.ts`, pantallas `ChooseProvider`, `ConfirmLocal`, `ConfirmRemote`, `RemoteWaiting`, `Success`, `AwaitingPin`, `CertRejected`, `AgentMissing`; pruebas que citaban esos textos.
- Panel Angular: `widget-dialog.ts` (tema en la URL), `sign.ts`/`sign.html`/`sign.spec.ts` restaurados, `widget-window.ts` y su prueba eliminados, `frontend/README.md`.
- Docs: `widget/README.md` (opción 3 con la advertencia; parámetro `theme`), `README.md` (1.2 y «Flujos a probar»).
- Sin cambios en el servidor ni en la API; el mensaje `firmadoc:*` y el soporte de `window.opener` del widget se mantienen.

## Fuera de alcance

- Quitar el modo ventana emergente del widget o de la página de ejemplo (sigue siendo una alternativa válida para integradores).
- Rediseñar las pantallas del widget más allá de quitar el marco y los textos de más.
