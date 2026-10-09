# Modo demostración (sin token USB)

Un solo comando prepara y arranca Firmadoc para probarlo sin token USB ni configuración manual:

```
python -m firmadoc.demo            # desde la raíz del repositorio, con el entorno virtual activo
python -m firmadoc.demo --port 8001
python -m firmadoc.demo --reset    # borra data/demo y empieza de cero
python -m firmadoc.demo --prepare-only   # prepara el entorno y no arranca el servidor
```

Al arrancar muestra la URL del panel, el token de acceso y la API key de demostración. Para firmar:

1. Abrí el panel con la dirección que imprime (`http://localhost:8000/panel`, el panel Angular; también está
   el estático en `/admin`; usá `localhost`, no `127.0.0.1`: el widget solo se embebe desde el origen configurado).
2. Ingresá con el token de acceso.
3. En **Firmar documento**, cargá uno o varios PDF y elegí **Firma propia**.

**Firma propia** es el proveedor `local`: firma electrónica de demostración con un certificado propio de Firmadoc.
No usa el token USB ni el agente y **no tiene la presunción legal de la firma digital** (Ley 25.506); sirve para
recorrer y evaluar todos los flujos.

## Qué crea

Todo queda en `data/demo/` (ignorado por git), sin tocar tu base ni tu `.env`:

| Archivo | Contenido |
|---|---|
| `firmadoc-demo.db` | base SQLite con el esquema completo y el seed de demostración |
| `storage/` | PDF de los documentos |
| `local-cert/` | certificado de demostración de «Firma propia» |
| `demo.json` | token de administración y secreto de los enlaces del widget (se generan una vez y se conservan) |

Los datos y los secretos son de demostración: no se usan en producción. Con `FIRMADOC_REAL_MODE=true` el comando se
niega a arrancar (ver `real-mode.md`).

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

## Fuera de la demo

La firma con token real o simulada (agente con certificado de software) no forma parte de este comando.
