# Modo demostración

Un solo comando prepara y arranca Firmadoc para probarlo sin token USB ni configuración manual (y, si tenés un
token físico con su middleware, también para firmar con él: ver más abajo):

```
python -m firmadoc.demo            # desde la raíz del repositorio, con el entorno virtual activo
python -m firmadoc.demo --port 8001
python -m firmadoc.demo --reset    # borra data/demo y empieza de cero
python -m firmadoc.demo --prepare-only   # prepara el entorno y no arranca el servidor
python -m firmadoc.demo --cuil 20123456789 --nombre "Titular del Token"   # el panel firma como el titular de un token físico
```

Al arrancar muestra la URL del panel, el token de acceso y la API key de demostración. Para firmar:

1. Abrí el panel con la dirección que imprime (`http://localhost:8000/panel`, el panel Angular; también está
   el estático en `/admin`; usá `localhost`, no `127.0.0.1`: el widget solo se embebe desde el origen configurado).
2. Ingresá con el token de acceso.
3. En **Firmar documento**, cargá uno o varios PDF y elegí **Firma propia**.

**Firma propia** es el proveedor `local`: firma electrónica de demostración con un certificado propio de Firmadoc.
No usa el token USB ni el agente y **no tiene la presunción legal de la firma digital** (Ley 25.506); sirve para
recorrer y evaluar todos los flujos. Los otros dos métodos también se pueden probar: **Firma con token** con un
token de software o con el token físico, y **Firma remota** con el servicio simulado (secciones de abajo).

## Qué crea

Todo queda en `data/demo/` (ignorado por git), sin tocar tu base ni tu `.env`:

| Archivo | Contenido |
|---|---|
| `firmadoc-demo.db` | base SQLite con el esquema completo, el seed de demostración **y los PDF** (tabla `stored_blob`, almacén `database`, como en una instalación real; ver `database.md`) |
| `storage/` | solo en entornos creados antes de que la demo guardara los PDF en la base: al arrancar, esos PDF se copian a la base (la guía dice cuántos) y los archivos quedan como copia, se pueden borrar. Si alguno falta o está corrupto, la demo no arranca y lo indica (`--reset` empieza de cero) |
| `local-cert/` | certificado de demostración de «Firma propia»; en `firmar-mock/`, la AC del servicio de firma remota simulado (se crea en la primera firma remota) |
| `demo.json` | token de administración, secreto de los enlaces del widget y secretos del servicio de firma remota simulado (cliente y callback); se generan una vez y se conservan, y un `demo.json` anterior se completa sin regenerar lo que ya tenía |

Los datos y los secretos son de demostración: no se usan en producción. Con `FIRMADOC_REAL_MODE=true` el comando se
niega a arrancar (ver `real-mode.md`).

## Con PostgreSQL

La misma demo puede correr sobre la base PostgreSQL del proyecto (o cualquier otra URL de SQLAlchemy), que es la
instalación recomendada para operar (`database.md`):

```bash
docker compose up -d postgres
python -m firmadoc.demo --database-url postgresql+psycopg://firmadoc:firmadoc@localhost:5432/firmadoc
```

Aplica las migraciones en esa base, carga el seed si no está y guarda los PDF en su tabla `stored_blob` (se ven desde
DBeaver). El resto del entorno (secretos, token de prueba, directorio de confianza, certificado de «Firma propia») sigue
en `data/demo/`, así que `firmadoc-demo.db` no se crea. La guía muestra la base en uso sin la contraseña.

`--reset` borra solo `data/demo/`; **no toca la base externa**. Para empezar de cero con la base del proyecto:
`docker compose down -v` (borra sus datos) y `docker compose up -d postgres`. Si la base tiene versiones cuyo PDF no
está en `stored_blob` (por ejemplo, cargadas con el almacén `files`), la demo no arranca e indica cómo migrarlos con
`storage_migrate` (`database.md`, «Pasar de archivos a la base»).

## Widget

El comando no compila el widget (necesita Node). Si falta, avisa y el panel funciona, pero no se verá el módulo de
firma. Para compilarlo:

```
cd widget
npm install
npm run build
```

## Panel Angular

Lo mismo vale para el panel Angular de `/panel` (`frontend/`): si no está compilado, `/panel` responde `503` y el
comando lo avisa; mientras tanto sirve el panel estático de `/admin`. Para compilarlo:

```
cd frontend
npm install
npm run build
```

Para desarrollarlo con `npm start` (recarga en caliente en `http://localhost:4200/panel/`) contra la demo, arrancá
la demo con `FIRMADOC_PANEL_ORIGINS=http://localhost:4200` en el entorno para que el widget acepte ese origen.

## Firma con token de prueba (sin hardware)

La demo genera una vez, en `data/demo/token/`, una **AC de prueba** (`ca.crt`) y un **certificado de firmante con
clave privada** (`firmante.pem`, titular «Firmante de Prueba», CUIL `20000000001`), confía en esa AC desde su propio
directorio de confianza (`data/demo/trust/`, sin tocar `backend/trust`) y configura al firmante del panel con ese
CUIL. Para recorrer la firma con token, en otra terminal (con el entorno virtual activo) arrancá Firmadoc Agent con
ese certificado como **token de software**:

```
firmadoc-agent run --software-token data/demo/token/firmante.pem --origin http://localhost:8000
```

(el comando exacto lo imprime la demo). Después, en el panel: cargá un PDF → **Firma con token** → elegí el
certificado → en la ventana del agente ingresá el PIN `1234`. La firma es PAdES verificable contra la AC de prueba;
el PIN nunca pasa por el navegador. Chrome/Edge pueden pedir una vez permiso de «acceso a la red local».

Todo esto es demostración: la clave privada vive en un archivo sin cifrar dentro de `data/demo/` y la AC no tiene
valor legal. El `.exe` instalado por política de dominio sigue usando un módulo PKCS#11 real.

## Firma remota con el servicio simulado

La demo también habilita el tercer método, **Firma remota**, contra el **servicio de firma remota simulado** que
corre en el mismo servidor (`/mock/firmar`, ver `firmar.md`): fija `FIRMADOC_FIRMAR_BASE_URL=http://localhost:8000/mock/firmar`
y `FIRMADOC_FIRMAR_MOCK_ENABLED=true`, con un secreto de cliente y uno de callback que guarda en `demo.json`. Para
recorrerlo, en el panel: cargá un PDF → **Firma remota** → **Firmar documento** → **Continuar en el servicio de
firma**. Se abre en otra pestaña la página del simulado (la pantalla que en un servicio real sería la del
usuario): ingresá el OTP `123456` y el PIN `1234` y elegí **Firmar** (o **Rechazar**). El simulado firma el PDF con
un certificado emitido por su propia AC y avisa a Firmadoc por el callback; el widget, que consulta el estado,
pasa solo a «Documento firmado» y la v2 queda en «Documentos», verificable contra la AC del simulado (que se suma a
las anclas mientras el simulado esté habilitado). Tres intentos fallidos bloquean la operación: cancelá en el
widget y empezá de nuevo. Como el resto de la demo, es una simulación: el contrato del servicio real no está
verificado y no hay convenio con él. La firma remota no se ofrece en lotes.

## Firma con el token físico desde la demo

La demo también sirve para firmar con un token criptográfico USB real. El servidor valida el certificado contra
`backend/trust/`, que ya trae las anclas de la **AC Raíz de la República Argentina** y de la **AC de Firma Digital
(ONTI)** (ver `backend/trust/README.md`); si tu certificado lo emitió otra AC, copiá su raíz e intermedia ahí
antes de arrancar. Pasos, en la PC donde está el token:

1. **Middleware del fabricante**, de 64 bits (el Python del agente es de 64 bits). Después de instalarlo, ubicá su
   biblioteca PKCS#11 (una `.dll` en `C:\Windows\System32`; su nombre depende del fabricante).
2. **Configuración del agente** en `%APPDATA%\FirmadocAgent\config.json`, con el origen exacto de la demo:
   ```json
   {
     "port": 47123,
     "allowed_origins": ["http://localhost:8000"],
     "pkcs11_module": "C:\\Windows\\System32\\<biblioteca-del-fabricante>.dll",
     "log_level": "INFO"
   }
   ```
3. **Diagnóstico sin PIN** (solo lectura): comprueba que la biblioteca carga y lista el certificado del token,
   con su emisor (para saber qué anclas hacen falta) y el CUIL del `serialNumber`:
   ```
   python -m firmadoc_agent --config "%APPDATA%\FirmadocAgent\config.json" diagnose
   ```
4. **Demo.** Alcanza con `python -m firmadoc.demo`: para firmar con token no se coteja el CUIL del certificado
   con el del firmante de la solicitud (lo único que se exige es el PIN del token), y la firma queda registrada
   con el titular real del certificado. Si querés que el panel muestre al titular del token como firmante de
   los PDF que cargue, arrancala con `--cuil <CUIL del diagnose> --nombre "<Titular>"` (`--email` opcional).
   Con `FIRMADOC_REQUIRE_CUIL_MATCH=true` en el entorno el servidor vuelve a exigir que el CUIL coincida
   (`403 cuil_mismatch`), y entonces `--cuil` sí tiene que ser el del certificado.
5. **Agente con el módulo PKCS#11**, en otra terminal (la demo imprime el comando con su puerto):
   ```
   python -m firmadoc_agent --config "%APPDATA%\FirmadocAgent\config.json" run --origin http://localhost:8000
   ```
   No uses `--software-token`: con esa opción el agente firma con el certificado de prueba, no con el token.
6. En el panel: cargá un PDF → **Firma con token** → elegí el certificado → el agente muestra el documento y pide
   el **PIN del token** en su propia ventana (un intento; un PIN incorrecto cuenta contra el límite del token).
   Chrome/Edge 142+ piden una vez permiso de «acceso a la red local» para llegar al agente en `127.0.0.1`.

La validación de revocación corre en `soft-fail`: el servidor intenta descargar la CRL de la AC y, si la red no lo
permite, sigue adelante marcando la revocación como no verificada. La **primera** validación de un certificado de
una AC descarga su CRL (la de firmantes de la AC ONTI pesa unos 9 MB: puede tardar desde unos segundos hasta
medio minuto según la red); las siguientes la reutilizan desde memoria hasta su `next_update` (en el registro del
servidor aparece «CRL incorporada a la caché» una sola vez). Si aun así la descarga molesta, arrancá la demo con
`FIRMADOC_REVOCATION_FETCH=false` en el entorno.

## Fuera de la demo

El modo real (`FIRMADOC_REAL_MODE=true`: PostgreSQL, revocación en `hard-fail`, sin datos de prueba) no forma parte
de este comando: ver `docs/real-mode.md`.
