## Context

- El proveedor `token` valida el certificado contra las anclas de `FIRMADOC_TRUST_DIR` y exige que el CUIL del sujeto (`serialNumber = "CUIL nnnnnnnnnnn"`) coincida con `signer.identifier`. El firmante por defecto del panel es «Operador del panel» con identificador `panel`: con token, `prepare` falla por `cuil_mismatch`.
- El agente (`cmd_run`) ya admite inyectar `backend` y `ui`; `SoftwareBackend`/`SoftwareToken` (`firmadoc_agent.testing`) implementan el contrato en memoria y los usan las pruebas e2e. `AgentConfig` solo se carga de `config.json`.
- La ventana Tk (`PinDialog`) muestra título, lista de documentos, sujeto completo, PIN y botones; no se centra ni fija su posición. Las pruebas del agente inspeccionan sus etiquetas, el `Listbox` y `entry`/`pin_var`.
- El PIN se ingresa solo en el agente (nunca en el navegador): README y `widget/README.md` lo establecen como invariante.

## Goals / Non-Goals

**Goals:** recorrer la firma con token desde el panel de la demo sin hardware; ventana del agente mínima, centrada y al frente; nada de esto debe aflojar el modo real.

**Non-Goals:** PIN en el navegador; token de software en el `.exe` instalado por política; cambios en el widget.

## Decisions

1. **La PKI de prueba la genera el servidor (`firmadoc/demo_pki.py`)**, no el agente: así el backend controla qué AC confía (la escribe en su directorio de confianza) y el agente solo carga «un certificado con su clave» desde un PEM, igual que haría con un token. Se persiste en `data/demo/token/` (`ca.crt`, `firmante.pem` con clave sin cifrar: solo demostración, carpeta ignorada por git) y se reutiliza entre arranques para que las firmas anteriores sigan verificándose.
2. **Directorio de confianza de la demo** `data/demo/trust/`: copia de `backend/trust/*.crt` más `demo-ca.crt`. No se toca `backend/trust` (anclas reales). `FIRMADOC_TRUST_DIR` apunta ahí solo en la demo. Revocación: la demo mantiene `soft-fail`; el certificado de prueba no publica CRL ni OCSP y la cadena se valida igual.
3. **Firmante del panel por configuración** (`panel_signer_*` en `Settings`): la demo lo fija a «Firmante de Prueba» / `20000000001` (el mismo firmante del seed), que es el CUIL del certificado de prueba. Alternativa descartada: saltar la verificación de CUIL cuando el identificador no es un CUIL (debilita la validación); pedir el firmante en el panel (más interfaz, fuera del pedido).
4. **`firmadoc-agent run --software-token RUTA [--origin O]... [--port N]`**: carga el PEM (`firmadoc_agent/software_token.py`, con `cryptography`, que ya es dependencia), arma `SoftwareBackend([token], pin="1234")` y usa la `TkUI` real. Los orígenes y el puerto vienen de la línea de comandos (si falta `config.json` se usan los valores por defecto; si existe, se respetan y `--origin` los reemplaza). El registro deja constancia de que es un token de software. `diagnose` también acepta `--software-token`.
5. **Ventana mínima**: titular (CN del sujeto) en grande, CUIL debajo en pequeño, «Va a firmar N documento(s)» con la lista compacta (hasta 4 filas visibles), PIN con foco, botones. Centrada con `geometry` tras `update_idletasks`, `-topmost`, `lift()` y `focus_force()`. Se conserva el sujeto completo como texto secundario para no perder información (y las pruebas existentes).
6. **Guía de la demo**: imprime el comando exacto del agente y el PIN; `docs/demo.md` agrega la sección «Firma con token de prueba».

## Risks / Trade-offs

- [Clave privada de prueba en disco sin cifrar] → solo en `data/demo/` (ignorado por git), AC de prueba sin valor legal; el modo real no la usa y `FIRMADOC_REAL_MODE` sigue rechazando la demo.
- [`--software-token` en el `.exe` instalado] → es una opción explícita de línea de comandos; `install.ps1` no la usa y el registro lo marca como demostración.
- [Chrome 142+ pide permiso de acceso a la red local] → documentado en `agent/README.md`; en la demo aparece una vez.

## Open Questions

- Ninguna.
