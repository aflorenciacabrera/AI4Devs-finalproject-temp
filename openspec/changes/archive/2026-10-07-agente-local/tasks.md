## 1. Paquete y configuración

- [x] 1.1 Crear `agent/pyproject.toml` (paquete `firmadoc_agent` en `agent/src/`, dependencias `python-pkcs11` y `cryptography`, extras `dev` y `build`) y registrar `agent/src` y `agent/tests` en el pytest y ruff de la raíz
- [x] 1.2 Instalar el agente en el entorno de desarrollo y confirmar que `python-pkcs11` importa en Windows
- [x] 1.3 Implementar `config.py`: carga del JSON (ruta por defecto y `FIRMADOC_AGENT_CONFIG`), valores predeterminados y validación estricta de puerto y orígenes
- [x] 1.4 Tests de configuración: sin archivo, origen con comodín o con ruta, puerto inválido

## 2. Núcleo sin hardware

- [x] 2.1 Definir `TokenBackend` (listar certificados; firmar una lista de hashes con un PIN) y los tipos `TokenCertificate`, y las excepciones de dominio con su `code`
- [x] 2.2 Implementar `SoftwareBackend` para tests con claves RSA reales, que firma `DigestInfo || hash` a mano igual que `CKM_RSA_PKCS`
- [x] 2.3 Definir `UserInterface` y `FakeUI` (acepta con PIN, cancela, agota el tiempo) 
- [x] 2.4 Implementar `service.py`: validar el pedido (algoritmo, 32 bytes, límites), listar certificados sin AC, y firmar (confirmación → un solo login → firmas → cierre de sesión en `finally`)
- [x] 2.5 Tests del servicio: lote de 3 con un solo PIN, cancelación sin login, PIN incorrecto con un único intento, PIN bloqueado, hash de otro algoritmo o longitud, certificado inexistente, error a mitad del lote sin firmas parciales y sesión cerrada

## 3. Servidor HTTP local

- [x] 3.1 Implementar `server.py` con `ThreadingHTTPServer` enlazado a `127.0.0.1`, solo `GET /certificates` y `POST /sign` y 404/405 para el resto
- [x] 3.2 Validación de `Origin` (exacto, obligatorio, sin comodines) y de `Host` (anti DNS rebinding)
- [x] 3.3 CORS: origen exacto (nunca `*`), preflight `OPTIONS` con `Access-Control-Allow-Private-Network`, `Content-Type` JSON obligatorio, cuerpo ≤ 1 MiB y ≤ 100 elementos
- [x] 3.4 Una firma simultánea: `429 busy`; cabecera `X-Firmadoc-Agent` y cuerpo de error `{code, detail}` en todas las respuestas
- [x] 3.5 Tests de seguridad por HTTP real: origen permitido y no permitido, sin `Origin`, `null`, `Host` ajeno, preflight de red privada, método y ruta inválidos, cuerpo grande y malformado, pedido concurrente

## 4. Backend PKCS#11 y diálogo

- [x] 4.1 Implementar `pkcs11_backend.py` con `python-pkcs11`: cargar el módulo, enumerar slots y tokens, leer certificados públicos (omitiendo AC) con su `CKA_ID`, y firmar con `Mechanism.RSA_PKCS`
- [x] 4.2 Mapear `PinIncorrect`, `PinLocked`, token ausente y módulo inexistente a las excepciones de dominio; leer el indicador de último intento
- [x] 4.3 Implementar `ui_tk.py`: diálogo modal siempre al frente, con nombres de documentos, sujeto del certificado, PIN enmascarado, advertencia de último intento y tiempo límite; ejecutado en el hilo principal con cola y `Future`
- [x] 4.4 Script `agent/scripts/try_dialog.py` para ver y probar el diálogo a mano, y test del diálogo que se omite si no hay pantalla
- [x] 4.5 Configurar SoftHSM: `conftest` que crea el token e importa una clave y su certificado de la PKI de prueba, activado por `SOFTHSM2_MODULE`; script `agent/scripts/softhsm-setup.sh`
- [x] 4.6 Tests con SoftHSM: listado de certificados, certificado de AC omitido, firma verificada con la clave pública, lote con un login, PIN incorrecto y sesión cerrada
- [x] 4.7 Ejecutar los tests de SoftHSM en WSL (Ubuntu) y dejar el workflow de CI (`.github/workflows/ci.yml`, job `agent`) que instala `softhsm2` y los corre

## 5. Punta a punta con el servidor

- [x] 5.1 Test que levanta el servidor Firmadoc (TestClient), el agente real sobre un puerto local con `SoftwareBackend` y `FakeUI`, y recorre `prepare` → agente `/sign` → `complete` con HTTP real y una PKI de prueba
- [x] 5.2 Casos: certificado de otra AC rechazado por el servidor antes del PIN, cancelación del usuario, PIN incorrecto y reintento manual, y lote de dos documentos con un solo PIN

## 6. Diagnóstico, registro y arranque

- [x] 6.1 Implementar `diagnose`: carga la biblioteca, lista slots, tokens y certificados (sujeto, emisor, serie, vigencia, uso de clave y `serialNumber` crudo) sin abrir sesión; código de salida correcto; `agent/diagnostico.py` como atajo
- [x] 6.2 Implementar `__main__`: subcomandos `run`, `diagnose` y `--version`, instancia única por el puerto ocupado, hilo del servidor y bucle de la UI en el hilo principal
- [x] 6.3 Registro con rotación (1 MiB × 3) sin PIN, firmas ni hashes completos; test que revisa el archivo tras una firma en nivel DEBUG
- [x] 6.4 Tests: diagnóstico con backend de software, biblioteca inexistente y segundo arranque con el puerto ocupado

## 7. Empaquetado e instalación

- [x] 7.1 Script de compilación con PyInstaller (`--onefile --noconsole`, incluye tkinter y python-pkcs11) y verificación de que `firmadoc-agent.exe --version` y `diagnose` funcionan
- [x] 7.2 `install.ps1` (copia a `%LOCALAPPDATA%\FirmadocAgent`, genera `config.json` desde `-Origin` y `-Pkcs11Module`, registra `HKCU\...\Run` y arranca) y `uninstall.ps1`; probarlos en una instalación real sin administrador
- [x] 7.3 Escribir `agent/README.md`: instalación manual, despliegue por política de dominio, política `LocalNetworkAccessAllowedForUrls`, arquitectura 32/64 bits del middleware, resolución de problemas y procedimiento de prueba manual con un token físico (carga de la biblioteca, lectura del certificado, lote con un solo PIN)

## 8. Contrato y cierre

- [x] 8.1 Ampliar `docs/agent-contract.md` con el contrato HTTP del agente (rutas, cuerpos, errores, orígenes, preflight, límites, `X-Firmadoc-Agent`) y verificar que coincide con los tests
- [x] 8.2 Ejecutar `pytest` y `ruff check` en todo el repositorio sin errores
