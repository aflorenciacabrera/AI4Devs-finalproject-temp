## 1. Widget sin marco y con tema

- [x] 1.1 `Screen.tsx` sin `.brandbar`; `app.css`: `body`/`.shell` transparentes y sin padding, `.card` sin borde/fondo/radio/franjas, `.actions` solo con línea superior; eliminar las reglas de `.brandbar`, `.brand` y `.chip`.
- [x] 1.2 `tokens.css`: colores oscuros bajo `:root[data-theme="dark"]` y `prefers-color-scheme: dark` (sin `data-theme="light"`); `main.tsx`: `?theme=light|dark` fija `data-theme`.
- [x] 1.3 Prueba del tema (`bootstrap` o `embed`): `theme=dark` → `data-theme="dark"`, valor raro → sin atributo.

## 2. Menos aclaraciones

- [x] 2.1 `messages/es.ts`: descripciones de los métodos en una línea; `ChooseProvider` sin leyenda al pie; `ConfirmRemote`, `RemoteWaiting`, `CertRejected`, `AgentMissing` sin leyenda; `ConfirmLocal` sin aviso de demostración; `Success` sin frase introductoria ni nota de versiones; `AwaitingPin` con aviso corto y pasos sin subtexto.
- [x] 2.2 Pruebas del widget y de navegador alineadas con los textos que quedan; `npm test`, `npm run lint`, `npm run build`.

## 3. Panel Angular

- [x] 3.1 `sign.ts`, `sign.html`, `sign.spec.ts` y `frontend/README.md` restaurados del commit anterior a FIRDOC-57; `widget-window.ts` y su prueba eliminados.
- [x] 3.2 `widget-dialog.ts`: `?theme=<tema del panel>` antes del fragmento; prueba; `ng test` y `ng build`.

## 4. Documentación y verificación

- [x] 4.1 `widget/README.md` (opción 3 con la advertencia de la dirección visible y sin citar al panel; parámetro `theme`; sin marco propio) y `README.md` (1.2, «Flujos a probar»).
- [x] 4.2 Suite e2e en Chrome en verde; en el panel contra la demo (claro y oscuro): el diálogo muestra el widget sin marco ni cabecera propios y se firma con «Firma propia». Verificado el 2026-10-13 en Chrome headless contra `python -m firmadoc.demo --port 8010`, en claro y en oscuro: sin `.brandbar` ni `.hint`, `data-theme` del widget igual al del panel, firma con «Firma propia» y diálogo cerrado con «Cerrar». Suite e2e: 43 pruebas en Chrome.
