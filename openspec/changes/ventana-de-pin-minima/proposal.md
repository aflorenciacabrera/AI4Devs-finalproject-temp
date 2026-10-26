## Why

La ventana del agente que pide el PIN muestra hoy el titular, el CUIL, el sujeto completo del certificado y la cantidad y lista de documentos. La usuaria pidió que muestre **solo el nombre del firmante y el campo de PIN**: menos texto, una sola decisión. Implementa **FIRDOC-51** (épica FIRDOC-18); HU «Firmar con token USB desde el sistema web».

## What Changes

- La ventana de PIN del agente queda con: el nombre del titular del certificado (CN) destacado, el campo de PIN con el foco inicial, y los botones Cancelar / Firmar. Se quitan el CUIL, el sujeto completo, la cantidad de documentos y la lista de nombres.
- Se conservan: ventana centrada y por encima de las demás, Enter/Escape, cierre por tiempo límite, borrado del PIN del widget al cerrar y la **advertencia de último intento** (es una alerta del token, no un dato del pedido).
- `SignPrompt` sigue llevando `document_names` y `certificate_subject`: el servicio los usa para el registro de actividad; el diálogo simplemente no los muestra.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `agent-token-signing`: «Confirmación del usuario antes de firmar» ya no exige mostrar los documentos ni el CUIL/sujeto; el diálogo muestra el nombre del titular y el PIN.

## Impact

- `agent/src/firmadoc_agent/ui_tk.py` (`PinDialog`), `agent/tests/test_agent_ui_tk.py`, `agent/scripts/try_dialog.py` (sin cambios funcionales: sigue pasando documentos, que ya no se ven).
- Documentación: `agent/README.md`, `docs/agent-contract.md` (flujo y «Requisitos del agente real»), `README.md` (criterio de aceptación de la HU que menciona el nombre del documento en el diálogo).
- Sin cambios en el servidor ni en el widget.

## Fuera de alcance

- Cambiar el contrato `POST /sign` (los nombres de documentos siguen viajando al agente y quedando en su registro).
- Rediseñar el widget.
