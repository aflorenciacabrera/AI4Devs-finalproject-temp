## Why

Por primera vez se probó el agente con un token criptográfico USB real (el dispositivo de referencia del proyecto, con el middleware PKCS#11 de 64 bits de su fabricante): `firmadoc_agent diagnose` carga la biblioteca y lista el certificado de usuario emitido por la **Autoridad Certificante de Firma Digital** de la ONTI, cuyo `serialNumber` trae el CUIL en el formato `CUIL nnnnnnnnnnn` que ya espera `extract_cuil`. Pero no se puede firmar de punta a punta: el modo demostración fija al firmante del panel con el CUIL ficticio del token de software (`20000000001`), por lo que el servidor responde `cuil_mismatch`, y el repositorio no incluye las anclas de la infraestructura de firma digital argentina, así que la cadena del certificado no es de confianza. Esto implementa **FIRDOC-49** (épica FIRDOC-18, «Proveedor token y Firmadoc Agent») y cierra el punto «Lo que todavía no está probado con hardware» de `docs/real-mode.md`; corresponde a la HU «Firmar con token USB desde el sistema web» del README.

## What Changes

- `python -m firmadoc.demo` acepta `--cuil`, `--nombre` y `--email` para configurar al firmante del panel con los datos del titular del token real. Sin esos parámetros, todo sigue igual (token de software, CUIL `20000000001`). `--cuil` exige 11 dígitos y `--nombre` es obligatorio junto con `--cuil`.
- La guía de la demo muestra el firmante configurado y, además del comando con token de software, el comando del agente con el módulo PKCS#11 de `%APPDATA%\FirmadocAgent\config.json` para firmar con el token físico.
- `backend/trust/` incorpora las anclas oficiales de la **AC Raíz de la República Argentina (2016)** y de la **Autoridad Certificante de Firma Digital (ONTI, 2026)**, en PEM, con sus huellas SHA-256 y el procedimiento de verificación documentados en su README. La demo ya copia `backend/trust/` a su directorio de confianza, de modo que el certificado del token real valida sin pasos extra.
- Documentación: `docs/demo.md` (sección «Firma con el token físico desde la demo»), `docs/real-mode.md` y `agent/README.md` registran el resultado de la prueba con hardware (biblioteca cargada, certificado listado, formato del CUIL confirmado) y qué queda por verificar con el PIN del titular.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `demo-mode`: nuevo requisito «Firmante real para el token físico» (`--cuil`/`--nombre`/`--email`), y la guía SHALL imprimir también el comando del agente con PKCS#11 y el firmante configurado.
- `trust-management`: nuevo requisito «Anclas de la infraestructura de firma digital argentina incluidas en el repositorio»: `backend/trust/` SHALL traer la AC Raíz 2016 y la AC de Firma Digital ONTI, y un certificado emitido por esa AC SHALL ser de confianza sin configuración adicional.

## Impact

- `backend/src/firmadoc/demo.py` (argumentos, `prepare`, `DemoEnv`, `guide`), `tests/test_demo.py`.
- `backend/trust/` (dos certificados PEM nuevos y README); `tests/` con una prueba que carga el directorio del repo y comprueba las dos anclas por huella.
- `docs/demo.md`, `docs/real-mode.md`, `agent/README.md`, `docs/agent-contract.md` (nota de «probado con hardware»).
- Sin cambios en el agente, el widget, la API ni el modelo de datos. Sin dependencias nuevas.

## Fuera de alcance

- Cambios en el agente o en el contrato agente–widget: la prueba con hardware no los requirió.
- El modo real completo (`FIRMADOC_REAL_MODE=true`, PostgreSQL, `hard-fail`): se documenta el camino, no se ejecuta en esta change.
- Firma del instalador del agente y despliegue por política de dominio.
- Consulta de revocación de la AC ONTI en `hard-fail` (la demo sigue en `soft-fail`).
- Nombrar en el repositorio al fabricante del token, al titular del certificado o al organismo: la documentación habla de «token de referencia» y «biblioteca del fabricante».
