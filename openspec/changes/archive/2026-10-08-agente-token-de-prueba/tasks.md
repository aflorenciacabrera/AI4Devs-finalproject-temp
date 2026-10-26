## 1. Backend: token de prueba en la demo

- [x] 1.1 `demo_pki.py`: AC de prueba y certificado de firmante con CUIL, persistidos en `data/demo/token/` y reutilizados
- [x] 1.2 `demo.py`: directorio de confianza `data/demo/trust/` (anclas del repo + AC de prueba), `FIRMADOC_TRUST_DIR`, firmante del panel y guía con el comando del agente y el PIN
- [x] 1.3 `Settings`: `panel_signer_name/identifier/email`; `panel_upload` los usa; `.env.example`
- [x] 1.4 Pruebas: generación y reutilización de la PKI, directorio de confianza, firmante del panel configurado, validación del certificado de prueba contra el servidor de la demo

## 2. Agente: token de software y ventana mínima

- [x] 2.1 `software_token.py`: carga de un PEM (clave + certificado) a `SoftwareToken`, con errores claros
- [x] 2.2 `__main__.py`: `run`/`diagnose` con `--software-token`, `--origin` y `--port`; configuración opcional; registro que indica token de software
- [x] 2.3 `ui_tk.py`: titular (CN) destacado, CUIL, lista compacta, foco en el PIN, ventana centrada y al frente
- [x] 2.4 Pruebas del agente: carga del PEM (válido e inválido), arranque con `--software-token` y `FakeUI`, etiquetas y colocación del diálogo

## 3. Documentación y cierre

- [x] 3.1 `docs/demo.md` («Firma con token de prueba»), `agent/README.md`, tabla de flujos del README
- [x] 3.2 Verificación en Chrome: demo + agente con token de software, firma con token desde el panel Angular
- [x] 3.3 `pytest`, `pytest agent/tests` y `ruff check` sin errores
