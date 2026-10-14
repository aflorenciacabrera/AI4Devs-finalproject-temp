## 1. Widget

- [x] 1.1 `RemoteWaiting.tsx`: `openServiceWindow` (ventana emergente centrada, nombre fijo), `onClick` con respaldo al enlace si la bloquean, cierre al desmontar, un segundo clic reemplaza la ventana.
- [x] 1.2 `widget/tests/choice.test.tsx`: el clic abre la ventana con `popup`, se cierra al llegar la firma (y al cancelar); si `window.open` devuelve `null` el enlace sigue su curso.

## 2. Simulado, pruebas de navegador y docs

- [x] 2.1 `mock_firmar.py`: textos de resultado («esta ventana se cierra sola»).
- [x] 2.2 `tests/e2e/test_provider_choice_e2e.py`: la ventana del simulado se cierra sola después de la firma.
- [x] 2.3 `docs/demo.md`, `widget/README.md`, `README.md`: ventana emergente en lugar de otra pestaña.

- [x] 2.4 Panel Angular: cabecera del diálogo «Firma de documento» / «Firma de documentos» (`sign.ts`, `sign.spec.ts`).

## 3. Verificación

- [x] 3.1 `npm test`, `npm run lint`, `npm run build` del widget; `pytest tests/test_firmar.py tests/test_demo.py`; suite e2e en Chrome; en la demo (panel Angular): «Continuar en el servicio de firma» abre una ventana emergente, con OTP y PIN se cierra sola y el widget muestra «Documento firmado». Verificado el 2026-10-13 contra `python -m firmadoc.demo --port 8010` en Chrome headless: ventana del simulado de 520×680, cerrada sola tras OTP y PIN, «Documento firmado» en el widget y cabecera «Firma de documento».
