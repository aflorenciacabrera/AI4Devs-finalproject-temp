## Context

El servidor y el contrato de firma ya están fijados (`docs/agent-contract.md`, specs `token-provider` y `certificate-validation`). El agente es la última pieza del modo principal: corre en la PC del funcionario, el navegador (widget) le habla por HTTP en `127.0.0.1`, y él es el único que toca el token. Los riesgos son tres: (1) la superficie de ataque de un servidor local que puede firmar, (2) el acceso al hardware y al PIN, (3) que el navegador lo deje usar (Chrome 142+ pide permiso para la red local). Se prioriza que casi toda la lógica de seguridad sea testeable sin token ni ventanas.

## Goals / Non-Goals

**Goals:**
- Un agente chico, con dos operaciones, que no firma nada que el usuario no haya confirmado con su PIN.
- Probar sin hardware: origen/Host, CORS/PNA, validación del pedido, flujo de PIN, lote, concurrencia, limpieza de sesión.
- Probar el tramo PKCS#11 con SoftHSM, y la integración real agente ↔ servidor.
- Instalación por usuario en Windows sin administrador.

**Non-Goals:**
- Widget, lote en el servidor, ECDSA, code signing, auto-actualización, bandeja del sistema, macOS/Linux de usuario, token físico (procedimiento manual).

## Decisions

1. **Servidor con `http.server` de la biblioteca estándar** (`ThreadingHTTPServer`), no FastAPI/uvicorn: el agente tiene dos rutas, y así el ejecutable queda mucho más liviano y con menos superficie. Alternativa descartada: FastAPI, por peso y dependencias sin beneficio aquí.
2. **Capas**: `server.py` (HTTP, orígenes, CORS), `service.py` (casos de uso: listar y firmar, validación del pedido), `backend.py` (`TokenBackend` Protocol), `pkcs11_backend.py` (implementación real), `ui.py` (`UserInterface` Protocol) y `ui_tk.py` (diálogo). `service.py` no importa tkinter ni PKCS#11: recibe backend y UI por inyección, y es donde se concentra y se prueba la política.
3. **Biblioteca PKCS#11: `python-pkcs11`** (ya prevista en el README; hay wheel para Windows con Python 3.13). Alternativa: PyKCS11, equivalente; se descarta por consistencia con el diseño documentado. Se aísla en `pkcs11_backend.py` para poder cambiarla.
4. **Firma con `CKM_RSA_PKCS`** sobre `DigestInfo || hash` armado por el agente, tal como lo verifica el servidor (`Prehashed(SHA256)` + PKCS#1 v1.5). El prefijo `DigestInfo` SHA-256 es una constante de 19 bytes. Se confirma con un token real en la prueba manual.
5. **Listado sin login**: los certificados son objetos públicos (`CKO_CERTIFICATE`/`CKC_X_509`), legibles sin PIN. No se filtran por la existencia de la clave privada porque muchos tokens ocultan las claves privadas hasta autenticarse. Se omiten los certificados de AC mirando `BasicConstraints.ca` y se identifican por `CKA_ID` (hex), que luego sirve para encontrar la clave privada con el mismo `CKA_ID` tras el login.
6. **Un solo login por pedido**: abrir sesión → `login(PIN)` → firmar N hashes → logout → cerrar. Cualquier excepción pasa por un `finally` que hace logout y cierra la sesión. Un PIN incorrecto produce exactamente un intento; el mapeo es `PinIncorrect → 401 pin_incorrect`, `PinLocked → 423 pin_locked`; el estado "último intento" se lee de `token.flags` (`USER_PIN_FINAL_TRY`) **antes** de pedir el PIN para advertirlo en el diálogo.
7. **Diálogo tkinter en el hilo principal**: tkinter exige su hilo; el servidor HTTP corre en otro. Los handlers publican un pedido en una cola y esperan un `Future`; el hilo principal atiende la cola con `root.after` y muestra un `Toplevel` modal, siempre al frente, con los nombres de los documentos, el sujeto del certificado, el campo de PIN enmascarado y Firmar/Cancelar. Tiempo límite de 120 s. El PIN se entrega al handler y el widget se destruye. Python no permite borrar strings de memoria de forma garantizada; se limita el tiempo de vida y se documenta.
8. **Seguridad del servidor local** (cada punto con test):
   - bind a `127.0.0.1` fijo (no configurable);
   - `Origin` obligatorio y coincidencia exacta con la lista (sin comodines, sin `null`);
   - `Host` ∈ {`127.0.0.1:puerto`, `localhost:puerto`} contra DNS rebinding;
   - respuesta CORS solo con el origen exacto, jamás `*`; preflight con `Access-Control-Allow-Private-Network`;
   - `Content-Type: application/json` obligatorio en `POST` (fuerza preflight CORS y descarta formularios), cuerpo ≤ 1 MiB, ≤ 100 elementos;
   - una firma simultánea (lock no bloqueante → `429 busy`);
   - el diálogo de confirmación con PIN es la defensa final: ningún origen permitido puede firmar sin que la persona lo vea y lo autorice.
9. **Errores**: `{"code","detail"}` con códigos estables; el widget los traduce. Códigos: `origin_not_allowed`, `host_not_allowed`, `invalid_request`, `too_many_items`, `token_not_found`, `certificate_not_found`, `pkcs11_unavailable`, `user_cancelled`, `pin_incorrect`, `pin_locked`, `busy`.
10. **Configuración** en `%APPDATA%\FirmadocAgent\config.json` (`port` 47123 por defecto, `allowed_origins`, `pkcs11_module`, `log_level`); `FIRMADOC_AGENT_CONFIG` la sobrescribe (útil en tests y en despliegues). Validación estricta al arrancar: orígenes `esquema://host[:puerto]` exactos.
11. **Diagnóstico** como subcomando (`firmadoc-agent diagnose`) más un `agent/diagnostico.py` mínimo que lo invoca (el README lo menciona). Muestra el `serialNumber` crudo del sujeto para resolver la pregunta abierta del formato del CUIL con un certificado real. Nunca abre sesión.
12. **Registro**: `logging` con `RotatingFileHandler` (1 MiB × 3) en `%LOCALAPPDATA%\FirmadocAgent\agent.log`. Se registran origen, operación, nombres de documentos, código de resultado y huella corta de certificado; nunca PIN, firmas ni hashes completos (solo los primeros 8 hex).
13. **Instancia única** por el propio bind del puerto (`OSError` → mensaje y salida ≠ 0); sin mutex adicional.
14. **Empaquetado**: PyInstaller `--onefile --noconsole`, con `tkinter` y `python-pkcs11` incluidos. Los scripts `install.ps1`/`uninstall.ps1` trabajan en `%LOCALAPPDATA%` y `HKCU`, sin administrador. Sin firma de código: SmartScreen puede advertir; se documenta la alternativa de firmar con el certificado del organismo y de distribuir por política de dominio.
15. **Pruebas**:
    - Unitarias y de seguridad sobre `service`/`server` con `SoftwareBackend` (claves RSA de `cryptography`, implementa `CKM_RSA_PKCS` a mano igual que el simulador del servidor) y `FakeUI`.
    - SoftHSM: `agent/tests/test_pkcs11_softhsm.py`, se activa con `SOFTHSM2_MODULE`; el token se crea en `conftest` con `python-pkcs11` (importa una clave y su certificado de la PKI de prueba). Se ejecuta en CI (Linux, `softhsm2`) y localmente en WSL (Ubuntu ya disponible). En Windows nativo se omite.
    - Punta a punta: servidor FastAPI (TestClient) + agente real sobre un socket local + `SoftwareBackend`; el "widget" lo hace el test con `http.client`.
    - El diálogo tkinter se prueba con una prueba manual guiada (script `agent/scripts/try_dialog.py`) y un test que lo instancia solo si hay pantalla.

## Risks / Trade-offs

- **Middleware del fabricante (alto):** la DLL PKCS#11 debe coincidir en arquitectura con el Python del agente; el comportamiento de tokens reales difiere de SoftHSM. Mitigación: diagnóstico claro, backend aislado, prueba manual documentada. Un token que no acepte `CKM_RSA_PKCS` con `DigestInfo` obligaría a revisar el contrato.
- **Aviso de red local de Chrome 142+:** sin la política el usuario ve un permiso la primera vez. Se documenta la política `LocalNetworkAccessAllowedForUrls` y se prueba la respuesta a la preflight de red privada.
- **tkinter/ventana oculta detrás de otras:** el diálogo se fuerza al frente (`-topmost`, foco); riesgo de que el usuario no lo vea, mitigado con un timeout y el mensaje `user_cancelled`.
- **Python empaquetado y antivirus:** los ejecutables de PyInstaller a veces generan falsos positivos; la firma de código del organismo y la distribución por política lo mitigan.
- **PIN en memoria:** no se puede borrar de forma garantizada en Python; se minimiza su vida y no se persiste ni registra.
- **Un solo puerto fijo:** conflicto con otra aplicación; es configurable, y el widget deberá leer el puerto de su propia configuración.
- **SoftHSM no es un token:** valida el código PKCS#11, no la compatibilidad con el hardware.

## Open Questions

- ¿Puerto predeterminado 47123 o uno que el organismo prefiera? Es configurable.
- ¿Cómo informa el widget el puerto si se cambia? Se resuelve en el change del widget.
- ¿El token del organismo acepta `CKM_RSA_PKCS` con `DigestInfo` y expone el certificado sin login? Se confirma con el dispositivo real.
