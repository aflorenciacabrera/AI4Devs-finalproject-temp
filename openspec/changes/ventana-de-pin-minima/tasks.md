## 1. Ventana de PIN

- [x] 1.1 `ui_tk.py`: `PinDialog` muestra solo «Firmar con el certificado de» + nombre del titular (CN o sujeto completo si no hay CN), la advertencia de último intento si corresponde, el campo de PIN y los botones; quitar CUIL, sujeto completo, cantidad y lista de documentos.
- [x] 1.2 `agent/tests/test_agent_ui_tk.py`: comprobar que no aparecen nombres de documentos, cantidad, CUIL ni sujeto, que el titular sí aparece y que la advertencia de último intento sigue; `pytest agent/tests -q` y `ruff check agent` en verde.

## 2. Documentación

- [x] 2.1 `agent/README.md` (párrafo «La ventana de confirmación muestra…»), `docs/agent-contract.md` (paso 4 del flujo y «Requisitos del agente real»), `README.md` (criterio de aceptación de la HU que menciona el nombre del documento en el diálogo).

## 3. Verificación

- [ ] 3.1 Reiniciar el agente y firmar desde el panel con el token: la ventana muestra solo el nombre y el PIN (lo ejecuta la titular del token).
