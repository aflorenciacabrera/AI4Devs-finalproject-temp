## Why

Todo lo probado hasta ahora usó el motor propio de demostración (`local`), un servicio de firma remota simulado, un token de software (SoftHSM) y datos de seed. Para operar con un **token físico real** (mToken CryptoID del PJ) hace falta que el servicio **no pueda arrancar ni operar por error en modo demostración**: sin la firma electrónica de demostración, sin simulados, con validación de revocación estricta y con confianza configurada explícitamente. Hoy esas protecciones dependen de que quien despliega no se equivoque de variable.

Backlog: FIRDOC-32 (modo real: operar con token físico y sin datos de demostración).

## What Changes

- **Modo real** (`real-mode`): `FIRMADOC_REAL_MODE=true`. Cambia tres cosas: (1) el servidor **no arranca** si la configuración no cumple los requisitos de un entorno real; (2) el proveedor `local` (firma electrónica de demostración) **deja de estar habilitado**; (3) `python -m firmadoc.seed` **se niega** a cargar datos de demostración.
- **Verificación previa** (`real-mode`): un conjunto de comprobaciones de configuración (`firmadoc.preflight`), usadas al arrancar en modo real y disponibles como comando (`python -m firmadoc.preflight`, código de salida distinto de cero si hay errores). Distingue **errores** (impiden arrancar), **advertencias** (se informan) y **avisos informativos**.
- **Guía** (`docs/real-mode.md`): paso a paso para pasar a modo real con el mToken CryptoID — software del fabricante, configuración del agente (`pkcs11_module`), diagnóstico sin PIN, anclas de la AC, ajuste del CUIL, y la lista de lo que **todavía no está probado con hardware**.
- Sin migraciones ni cambios de API. El modo demostración (valor por defecto) se comporta exactamente como hasta ahora.

## Capabilities

### New Capabilities

- `real-mode`: modo real, verificación previa y guía de puesta en producción con token físico.

### Modified Capabilities

- Ninguna.

## Impact

- Servidor: `preflight.py` (nuevo), `config.py`, `main.py` (arranque), `providers/__init__.py`, `seed.py`.
- Documentación: `docs/real-mode.md`, `.env.example`, `backend/README.md`.

## Fuera de alcance

- La prueba con el token físico y el ajuste de `extract_cuil` al certificado real: dependen de instalar el software del fabricante y de ver el certificado (se hacen con el diagnóstico del agente; ver la guía).
- Descargar o validar automáticamente las raíces de la AC: se cargan a mano desde la fuente oficial, confirmando la huella por otro canal.
- Firmar el instalador del agente y desplegarlo por política de dominio.
