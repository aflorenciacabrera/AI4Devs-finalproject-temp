# Modo real (token físico, sin demostración)

`FIRMADOC_REAL_MODE=true` hace que Firmadoc **no arranque** con una configuración insegura o de demostración, que
**no habilite** la firma electrónica de demostración (`local`) y que el seed **no cargue** datos de prueba.
Sin esa variable todo funciona como en desarrollo.

## 1. Preparar la PC del firmante (agente + token)

1. Instalar el software del fabricante del token. Para el token de referencia, de **64 bits** (el Python
   del agente es de 64 bits). Después de instalar, buscar su biblioteca PKCS#11 (una `.dll` en
   `C:\Windows\System32`, su nombre depende del fabricante y de la versión).
2. Crear la configuración del agente, `%APPDATA%\FirmadocAgent\config.json`:
   ```json
   {
     "port": 47123,
     "allowed_origins": ["https://firmadoc.su-organismo.example"],
     "pkcs11_module": "C:\\Windows\\System32\\<biblioteca-pkcs11-del-fabricante>.dll",
     "log_level": "INFO"
   }
   ```
   `allowed_origins` son los sitios (exactos) desde los que se abre el widget.
3. Con el token conectado, **diagnosticar sin PIN** (`--config` va antes del subcomando):
   ```powershell
   python -m firmadoc_agent --config "$env:APPDATA\FirmadocAgent\config.json" diagnose
   ```
   (o `firmadoc-agent.exe --config ... diagnose`). Lista los certificados del token sin pedir el PIN. **Anotar**: el
   `serialNumber` del sujeto (cómo viene el CUIL) y la **autoridad certificante** que lo emitió.

## 2. Confianza

- `backend/trust/` ya trae la **AC Raíz de la República Argentina (2016)** y la **AC de Firma Digital de la ONTI
  (2026)**, con sus huellas y fuentes en `backend/trust/README.md`. Si el certificado lo emitió otra AC, descargar
  su **raíz e intermedia** de la fuente oficial y copiarlas en `backend/trust/` (`.crt`/`.pem`), o agregarlas desde
  el panel `/admin`. Confirmar siempre la **huella SHA-256 por otro canal**: una raíz de origen dudoso invalida toda
  la validación.
- **CUIL**: el servidor lo busca en el `serialNumber` del sujeto con formato `CUIL 20123456789`
  (`extract_cuil` en `certificate_validation.py`). Los certificados de la AC ONTI del token de referencia lo traen
  exactamente así (confirmado con `diagnose`). Si otra AC lo trae distinto, hay que ajustar esa función: es un único
  lugar y tiene pruebas.
- **Revocación**: el modo real exige `hard-fail`. Hace falta que el servidor pueda consultar la CRL/OCSP de la AC
  (`FIRMADOC_REVOCATION_FETCH=true`) o tener CRL locales en `FIRMADOC_CRL_DIR`.

## 3. Servidor

```powershell
$env:FIRMADOC_REAL_MODE = "true"
$env:FIRMADOC_DATABASE_URL = "postgresql+psycopg://usuario:clave@host:5432/firmadoc"
$env:FIRMADOC_STORAGE_BACKEND = "database"
$env:FIRMADOC_SIGNING_SECRET = "<32+ caracteres aleatorios>"
$env:FIRMADOC_ADMIN_TOKEN = "<32+ caracteres aleatorios>"
$env:FIRMADOC_REVOCATION_MODE = "hard-fail"
$env:FIRMADOC_REVOCATION_FETCH = "true"
$env:FIRMADOC_PUBLIC_BASE_URL = "https://firmadoc.su-organismo.example"
$env:FIRMADOC_TRUST_DIR = "backend/trust"

python -m firmadoc.preflight       # revisa la configuración; debe terminar sin errores
alembic upgrade head
python -m firmadoc.integrators create --name "Gestor documental" --origins https://gestor.su-organismo.example
uvicorn firmadoc.main:app
```

`python -m firmadoc.preflight` informa **errores** (impiden arrancar en modo real), **advertencias** y datos
informativos. Si hay errores, el servidor tampoco arranca: lista todos juntos.

En modo real: `provider: local` responde `422`, `provider: token` es el método de firma digital y `python -m
firmadoc.seed` se niega (los integradores reales se crean con `firmadoc.integrators`).

## 4. Primera firma con el token

1. Crear una solicitud con `provider: token` y los datos **reales** del firmante (nombre, CUIL, correo).
2. Abrir su `signing_url`: el widget detecta el agente, lista el certificado, **valida** (cadena, vigencia,
   revocación, CUIL) y recién entonces el agente pide el PIN.
3. Verificar el resultado con `POST /api/v1/documents/{id}/verify` y con una herramienta independiente
   (por ejemplo, Adobe Acrobat con la raíz instalada, o `openssl cms -verify`).

## Probado con hardware (token de referencia, octubre de 2026)

- La **biblioteca PKCS#11 del fabricante** (64 bits) carga desde el agente; `diagnose` lista el token y su
  certificado de usuario, emitido por la AC de Firma Digital de la ONTI, con usos de clave `digital_signature` y
  `non_repudiation`.
- El **CUIL** viene en el `serialNumber` del sujeto como `CUIL nnnnnnnnnnn`: `extract_cuil` no necesitó cambios.
- La **cadena** del certificado (AC de Firma Digital → AC Raíz de la República Argentina) valida contra las anclas
  incluidas en `backend/trust/`.
- La demo firma como el titular del token con `python -m firmadoc.demo --cuil ... --nombre ...` (`docs/demo.md`).

## Lo que todavía no está probado con hardware

- La **firma con la clave del token** (`CKM_RSA_PKCS` con `DigestInfo` SHA-256) con el PIN del titular, y el PDF
  resultante de punta a punta. El procedimiento está en `agent/README.md` («Prueba manual con un token físico»).
- La **consulta de revocación** de la AC ONTI en `hard-fail` (CRL `http://pki.jgm.gov.ar/crl/FD.crl` y OCSP
  `http://pki.jgm.gov.ar/ocsp`, según la AIA del certificado).
- El **instalador** del agente no está firmado y no se desplegó por política de dominio.
- El permiso de red local del navegador (Chrome) para que el widget llegue al agente en `127.0.0.1`.
