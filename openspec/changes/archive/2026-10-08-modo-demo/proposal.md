## Why

Quien prueba Firmadoc sin token USB tiene hoy que armar el entorno a mano: elegir una base, crear carpetas, generar un token de administración y un secreto para los enlaces del widget, aplicar migraciones, cargar el seed y arrancar el servidor. La firma «Firma propia» (proveedor `local`) ya funciona sin token, pero llegar a usarla requiere conocer todo eso. Implementa **FIRDOC-46**: un solo comando que deja el sistema en modo demostración listo para usar.

## What Changes

- Nuevo módulo `python -m firmadoc.demo` (con `--port`, `--host` y `--reset`) que prepara un entorno de demostración aislado en `data/demo/` y arranca el servidor.
- Genera una sola vez y conserva el token de administración y el secreto de los enlaces del widget, para que no cambien entre arranques.
- Aplica las migraciones, carga el seed de demostración (con los PDF en el almacenamiento) y configura `public_base_url` según el puerto, de modo que el panel pueda embeber el widget.
- Rechaza arrancar con `FIRMADOC_REAL_MODE` activo, avisa si falta compilar el widget y muestra la URL del panel, el token y el método a usar.
- Documentación en `docs/demo.md`.

## Capabilities

### New Capabilities
- `demo-mode`: preparación y arranque de un entorno de demostración sin token USB con un solo comando.

### Modified Capabilities
<!-- Ninguna: no cambia el comportamiento de capacidades existentes. -->

## Impact

- Código: nuevo `backend/src/firmadoc/demo.py`; sin cambios en la API ni en el esquema.
- Archivos: crea `data/demo/` (base SQLite, almacenamiento, certificado de demostración y `demo.json` con los secretos); ya está ignorado por git si `data/` lo está (se verifica).
- Docs: `docs/demo.md`.
- Dependencias: ninguna nueva (usa `uvicorn` y `alembic`, ya presentes).

## Fuera de alcance

- Token USB simulado (agente con certificado de software): quedaría como cambio aparte si se necesita probar «Firma con token» sin hardware.
- Despliegue público de la demo (FIRDOC-42) y contenedores.
- Modo real: este comando es exclusivamente de demostración y no lo habilita ni lo relaja.
