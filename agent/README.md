# Firmadoc Agent

Aplicación local que corre en la PC del funcionario y **firma hashes con el token** de firma digital por PKCS#11. Es la pieza que hace posible el proveedor `token` de Firmadoc: el navegador no puede acceder a un token USB, el servidor tampoco, y el PDF nunca viaja a la PC.

- **El agente solo lista certificados públicos y firma hashes.** No descarga el PDF, no tiene credenciales de Firmadoc y no se conecta con el servidor: el widget (en el navegador) hace de puente.
- **El PIN se ingresa solo en esta PC**, en un diálogo del agente. No se guarda, no se registra y no viaja a ninguna parte. El agente nunca lo reintenta por su cuenta (un PIN erróneo cuenta contra el límite de intentos del token).
- Contrato completo con el widget y el servidor: [`docs/agent-contract.md`](../docs/agent-contract.md).

## Requisitos

- Windows 10/11 (el código es portable, pero solo se prueba en Windows y, con SoftHSM, en Linux).
- El **middleware PKCS#11 del fabricante** del token, de la **misma arquitectura (32/64 bits)** que el agente. El ejecutable que se genera con `build.ps1` es de la arquitectura del Python con el que se compila.
- Para compilar: Python 3.11+ y `pip install -e "agent[build]"`.

## Instalación

### 1. Compilar el ejecutable

```powershell
pip install -e "agent[build]"
powershell -ExecutionPolicy Bypass -File agent\packaging\build.ps1     # genera agent\dist\firmadoc-agent.exe
```

### 2. Instalar para el usuario (sin administrador)

```powershell
agent\packaging\install.ps1 `
  -Origin https://firmadoc.example.org `
  -Pkcs11Module "C:\Windows\System32\<biblioteca-pkcs11-del-fabricante>.dll"
```

`-Origin` es el origen **exacto** desde el que se sirve el widget (esquema, host y puerto; sin comodines ni rutas). Puede repetirse. El script:

1. copia el ejecutable a `%LOCALAPPDATA%\FirmadocAgent`;
2. crea `%APPDATA%\FirmadocAgent\config.json` (si ya existe lo conserva; `-Force` lo reemplaza);
3. registra el arranque con la sesión (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`);
4. inicia el agente y comprueba que escuche en `127.0.0.1`.

Desinstalar: `agent\packaging\uninstall.ps1` (con `-KeepLogs` conserva el registro de actividad).

### 3. Despliegue por política de dominio

En equipos administrados, ejecutar `install.ps1` como **script de inicio de sesión** (GPO → Configuración de usuario → Directivas → Configuración de Windows → Scripts → Inicio de sesión) con los mismos parámetros, desde un recurso compartido que contenga `firmadoc-agent.exe` e `install.ps1` (usar `-ExePath` si no están en la misma carpeta). Una reinstalación actualiza el ejecutable y conserva la configuración.

El ejecutable **no está firmado digitalmente**: SmartScreen o el antivirus pueden advertirlo. En un despliegue institucional conviene firmarlo con el certificado de firma de código del organismo y distribuirlo solo desde el recurso compartido.

### Configuración (`config.json`)

| Clave | Por defecto | Uso |
|---|---|---|
| `port` | `47123` | puerto en `127.0.0.1` (1024–65535) |
| `allowed_origins` | `[]` | orígenes exactos que pueden usar el agente; con la lista vacía **se rechaza todo** |
| `pkcs11_module` | — | ruta de la biblioteca PKCS#11 del fabricante |
| `log_level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

La ruta del archivo se puede cambiar con `FIRMADOC_AGENT_CONFIG` o `--config`. Las claves desconocidas y los orígenes mal formados impiden el arranque con un mensaje claro.

El registro de actividad está en `%LOCALAPPDATA%\FirmadocAgent\agent.log` (rotación de 1 MiB, 3 copias). Registra origen, operación, nombres de documentos y resultado; **nunca** el PIN, las firmas ni los hashes completos.

## Navegador: aviso de acceso a la red local (Chrome/Edge 142+)

Desde Chrome 142 una página pública que llama a `127.0.0.1` muestra un pedido de permiso de **acceso a la red local** la primera vez. En equipos administrados se evita con la política `LocalNetworkAccessAllowedForUrls`, apuntando al **origen donde se sirve el widget** (el mismo que `allowed_origins`):

| Navegador | Política (registro) |
|---|---|
| Chrome | `HKLM\SOFTWARE\Policies\Google\Chrome\LocalNetworkAccessAllowedForUrls` |
| Edge | `HKLM\SOFTWARE\Policies\Microsoft\Edge\LocalNetworkAccessAllowedForUrls` |

Cada valor numerado (`1`, `2`, …) es una URL, por ejemplo `https://firmadoc.example.org`. También puede desplegarse con las plantillas ADMX de cada navegador. Verificar el nombre y el efecto en `chrome://policy` / `edge://policy` con la versión instalada, porque el comportamiento del navegador cambia entre versiones. El agente responde la *preflight* de acceso a red privada (`Access-Control-Allow-Private-Network: true`) para los orígenes permitidos.

## Diagnóstico

```powershell
firmadoc-agent.exe diagnose          # o: python agent\diagnostico.py
```

Verifica que la biblioteca PKCS#11 cargue, lista los slots, los tokens y los certificados (sujeto, emisor, serie, vigencia, uso de clave y el atributo `serialNumber` del sujeto, que es donde el servidor espera el CUIL). **No pide el PIN ni abre sesión.** Códigos de salida: `0` correcto, `1` la biblioteca no carga, `2` no hay token.

Problemas frecuentes:

| Síntoma | Causa probable |
|---|---|
| `pkcs11_unavailable` / "no se pudo cargar la biblioteca" | ruta incorrecta o arquitectura distinta (agente de 64 bits con DLL de 32, o al revés) |
| `token_not_found` | token no conectado, sin inicializar o middleware no instalado |
| el widget no detecta el agente | agente detenido, puerto distinto, o el origen del widget no está en `allowed_origins` (`origin_not_allowed`) |
| `pin_locked` | token bloqueado: se desbloquea con el PUK / el administrador del token, no con Firmadoc |

## Token de software (solo demostración)

Para recorrer la firma con token sin hardware, el agente puede usar como único certificado el de un archivo PEM
(clave privada sin cifrar + certificado), aceptando el PIN `1234`:

```
firmadoc-agent run --software-token data/demo/token/firmante.pem --origin http://localhost:8000 [--port 47123]
firmadoc-agent diagnose --software-token data/demo/token/firmante.pem
```

No hace falta `config.json` ni módulo PKCS#11; `--origin` (repetible) y `--port` reemplazan a los del archivo si
existe. El modo demostración del servidor (`python -m firmadoc.demo`) genera ese PEM y confía en su AC de prueba
(`docs/demo.md`). El registro de actividad marca el arranque como «TOKEN DE SOFTWARE»; `install.ps1` no usa esta
opción y el ejecutable instalado sigue exigiendo PKCS#11.

La ventana de confirmación muestra el titular del certificado, el CUIL, el o los documentos y el campo de PIN;
aparece centrada y por encima de las demás ventanas (incluido el navegador). El PIN se ingresa solo ahí: nunca en
el navegador ni en el widget.

## Prueba manual con un token físico

Pendiente de ejecutar con el dispositivo (el proyecto prevé un token criptográfico USB de referencia). Procedimiento:

1. Instalar el middleware del fabricante y ubicar su DLL PKCS#11.
2. `firmadoc-agent.exe --config <config.json> diagnose`: debe cargar la biblioteca y listar el certificado de usuario. **Anotar el valor de `serialNumber`**: confirma si el CUIL tiene el formato `CUIL 20123456789` que espera el servidor (pregunta abierta del diseño) y qué AC emitió el certificado (para cargar las anclas en `backend/trust/`).
3. `python agent\scripts\manual_token_test.py --module <DLL>`: pide el PIN **una sola vez**, firma un lote de 3 hashes con un único login y verifica cada firma con la clave pública del certificado. Un PIN erróneo cuenta como un intento contra el límite del token; el script no reintenta.
4. Resultado esperado: `RESULTADO: CORRECTO`. Si el token no acepta `CKM_RSA_PKCS` con el `DigestInfo` de SHA-256, hay que revisar el contrato (`docs/agent-contract.md`) antes de seguir.
5. Prueba de punta a punta: con el servidor configurado (anclas de la AC del token cargadas) y el agente instalado, firmar un documento desde el widget y verificar el PDF resultante.
6. Probar el diálogo con `python agent\scripts\try_dialog.py` (nombres largos, varios documentos, `--ultimo-intento`).

## Desarrollo

```powershell
pip install -e "agent[dev]"
pytest agent/tests                      # sin hardware: SoftwareBackend y UI de prueba
```

Pruebas con SoftHSM (PKCS#11 por software, Linux/WSL):

```bash
source agent/scripts/softhsm-setup.sh   # localiza libsofthsm2.so y softhsm2-util
pytest agent/tests                      # ahora también corre tests/test_agent_pkcs11.py
```

SoftHSM valida el código PKCS#11, no la compatibilidad con un token real. Tampoco emula el bloqueo del PIN: esa parte se prueba con un token falso (`test_agent_pkcs11_mapping.py`).

Estructura (`src/firmadoc_agent/`): `server.py` (HTTP y controles de origen), `service.py` (política de firma, sin HTTP ni hardware), `backend.py` / `pkcs11_backend.py` (el token), `ui.py` / `ui_tk.py` (confirmación y PIN), `config.py`, `diagnose.py`, `selftest.py`, `logs.py`.
