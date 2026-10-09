## Why

El modo demostración solo permite «Firma propia»: la firma con token, que es el modo principal de Firmadoc, hoy únicamente se ejercita en las pruebas automáticas (token de software en memoria) o con SoftHSM en WSL. Para un evaluador en Windows sin token físico el widget muestra «No detectamos Firmadoc Agent» y el flujo principal (certificado → confirmación → PIN en el agente → PAdES verificable) queda sin recorrer. Además, la ventana del agente mezcla título, lista, sujeto completo del certificado y PIN; la usuaria pidió una ventana mínima (titular y PIN), centrada y al frente del navegador.

Implementa **FIRDOC-48** (épica FIRDOC-5, entrega) y la HU del README «Como evaluador o usuario sin token físico, quiero firmar con el motor propio y con un token de software, para recorrer todos los flujos sin hardware».

## What Changes

- **Token de prueba en la demo**: `python -m firmadoc.demo` genera (una vez, en `data/demo/token/`) una AC de prueba y un certificado de firmante con CUIL `20000000001` («Firmante de Prueba»), arma un directorio de confianza propio (`data/demo/trust/`: las anclas del repositorio más la AC de prueba) y configura al firmante del panel con ese CUIL, para que la validación del certificado pase.
- **Agente con token de software**: `firmadoc-agent run --software-token data/demo/token/firmante.pem --origin http://localhost:8000` arranca el agente con ese certificado y su clave en memoria (PIN `1234`), con la ventana real de confirmación, sin `config.json` ni módulo PKCS#11. Solo para demostración: lo dice el registro y la ventana.
- **Ventana de PIN mínima**: la confirmación del agente muestra el nombre del titular del certificado (CN) en grande, el o los documentos a firmar y el campo de PIN; centrada en la pantalla y siempre al frente, con foco en el PIN. Se mantiene la advertencia de último intento.
- **Firmante del panel configurable**: `FIRMADOC_PANEL_SIGNER_NAME`, `FIRMADOC_PANEL_SIGNER_IDENTIFIER` y `FIRMADOC_PANEL_SIGNER_EMAIL` (por defecto los valores actuales).
- **Guía y documentación**: la demo imprime el comando del agente y el PIN; `docs/demo.md`, `agent/README.md` y la tabla de flujos del README lo explican.

## Fuera de alcance

- Ingresar el PIN en el navegador o en el diálogo del panel Angular: el PIN nunca sale de la PC ni pasa por el widget (decisión de seguridad del proyecto).
- Token de software para el modo real o producción; el `.exe` instalado sigue exigiendo PKCS#11.
- Cambios en el widget o en el panel Angular.

## Capabilities

### Modified Capabilities
- `demo-mode`: token de prueba, directorio de confianza de la demo y guía con el comando del agente.
- `agent-distribution`: modo `--software-token` del agente.
- `agent-token-signing`: contenido y colocación de la ventana de confirmación y PIN.
- `pdf-upload-signing`: firmante del panel configurable.

## Impact

- Backend: `demo.py`, nuevo `demo_pki.py`, `config.py`, `services/panel_upload.py`, `.env.example`.
- Agente: `__main__.py`, nuevo `software_token.py`, `ui_tk.py`.
- Pruebas: `tests/test_demo.py`, `tests/test_panel_upload.py`, `agent/tests/`.
- Docs: `docs/demo.md`, `agent/README.md`, `README.md`.
