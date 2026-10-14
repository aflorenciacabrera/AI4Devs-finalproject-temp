## 1. Widget: ventana propia

- [x] 1.1 `hostMessages.ts`: destinatario `parent` si está enmarcado, si no `opener` (descartar si falta o está cerrado); `closed()` cierra la ventana propia después de avisar (`closeWindow` inyectable); `main.tsx` si hace falta.
- [x] 1.2 `widget/tests/embed.test.ts`: con `opener` falso se envía a cada origen permitido y nunca a `"*"`; sin `opener` o cerrado no se envía; `closed()` cierra solo en ventana propia; enmarcado se usa `parent` aunque haya `opener`.

## 2. Página de ejemplo y guías

- [x] 2.1 `widget/examples/host.js` y `host.html`: `mode=popup` con botón «Abrir la firma en una ventana», validación por ventana y origen, registro de mensajes y del cierre.
- [x] 2.2 `widget/README.md`: «Opción 3: ventana emergente» (snippet, gesto del usuario, `window.open` nulo, cuándo elegirla, permiso de red local sin `allow`), variante Angular; `README.md` 1.2 (de «no implementada» a opción 3) y supuesto 7.

## 2b. Panel Angular en ventana propia

- [x] 2b.1 `widget-window.ts`: servicio que reserva la ventana en el gesto del usuario (`window.open` con página de espera), la navega a la `signing_url`, valida los mensajes por ventana y origen, detecta el cierre (`closed` por sondeo) y expone `focus`/`close`.
- [x] 2b.2 `sign.ts`/`sign.html`: reservar la ventana en «Cargar y firmar» antes de subir; abrir en la ventana y, si fue bloqueada, en el diálogo; «Ir a la ventana de firma»; aviso al cerrar sin firmar; `reset`/`replace`/destroy cierran la ventana.
- [x] 2b.3 `widget-window.spec.ts` y `sign.spec.ts` (ventana, bloqueo → diálogo, resultados, cierre sin firmar); `frontend/README.md`.

## 3. Prueba en Chrome y Edge

- [x] 3.1 `tests/e2e/conftest.py`: `FIRMADOC_E2E_BROWSER` (`chrome` | `msedge`), valor desconocido → error claro, navegador ausente → omitir.
- [x] 3.2 `tests/e2e/test_widget_e2e.py`: firma `local` en ventana emergente (`expect_page`), `firmadoc:signed` en la anfitriona, «Cerrar» cierra la ventana y llega `firmadoc:closed`.
- [x] 3.3 Documentar en `README.md` («Flujos a probar» o requisitos) cómo correr la suite en Chrome y en Edge; Firefox y Safari no verificados.
- [x] 3.4 Suite e2e en verde en Chrome y en Edge; `npm run build`, `npm test` y `npm run lint` del widget en verde.

## 4. Verificación

- [x] 4.1 Suite en navegador real: 43 pruebas en Chrome y 43 en Edge (`FIRMADOC_E2E_BROWSER=msedge`), 2026-10-13. Panel Angular contra `python -m firmadoc.demo --port 8010` en Chrome headless: el widget se abre en una ventana propia (sin diálogo), se firma con «Firma propia», la tarjeta muestra el resultado, «Cerrar» cierra la ventana y el botón vuelve a «Abrir módulo de firma».
