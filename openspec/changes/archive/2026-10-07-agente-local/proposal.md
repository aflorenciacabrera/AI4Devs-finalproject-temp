## Why

El servidor ya sabe validar el certificado de un token y verificar firmas hechas con él (change `proveedor-token`), pero hoy lo único que firma son los tests, con un simulador. Falta el componente que corre en la PC del funcionario, accede al token por PKCS#11, pide el PIN y firma el hash. Sin el agente, el modo principal de Firmadoc (firma digital con token) no es usable.

Es también el punto de mayor riesgo técnico del proyecto (acceso al hardware, PIN, permisos del navegador sobre `127.0.0.1`, empaquetado), por eso se construye detrás de una interfaz de backend de token que permite probar casi todo sin hardware, y se valida el tramo PKCS#11 con SoftHSM.

Backlog: FIRDOC-21 (agente local), FIRDOC-20 (firma con token, tramo del agente), FIRDOC-22 (el agente ya firma varios hashes con un solo PIN; el lote en el servidor queda aparte).

## What Changes

- Nuevo paquete `agent/` (Firmadoc Agent), en Python, con su propio `pyproject.toml`.
- **API local** (`agent-local-api`): servidor HTTP en `127.0.0.1` con solo dos operaciones, `GET /certificates` y `POST /sign`, que acepta pedidos únicamente de orígenes permitidos, valida la cabecera `Host` (anti DNS rebinding) y responde la preflight CORS y de acceso a red privada que exige Chrome 142+.
- **Firma con token** (`agent-token-signing`): lista los certificados públicos del token; firma cada hash con `CKM_RSA_PKCS` sobre el `DigestInfo` SHA-256 (el formato fijado en `docs/agent-contract.md`); muestra un diálogo de confirmación con el nombre de los documentos y pide el PIN una sola vez por lote; nunca reintenta un PIN.
- **Distribución y diagnóstico** (`agent-distribution`): configuración en un archivo JSON, comando de diagnóstico que lista certificados y verifica la biblioteca PKCS#11 sin pedir PIN, ejecutable único con PyInstaller y scripts de instalación por usuario para Windows.
- Interfaces `TokenBackend` (PKCS#11 real y un backend por software para tests) e `UserInterface` (diálogo tkinter y un doble para tests), de modo que la lógica de seguridad se prueba sin hardware ni ventanas.
- Pruebas de integración del tramo PKCS#11 con SoftHSM (en CI y, localmente, en WSL) y una prueba de punta a punta agente ↔ servidor sobre HTTP real.
- Ampliación de `docs/agent-contract.md` con el contrato HTTP completo del agente.

## Capabilities

### New Capabilities

- `agent-local-api`: API HTTP local, control de orígenes y de `Host`, CORS y acceso a red privada, códigos de error y límites.
- `agent-token-signing`: listado de certificados, firma de hashes por PKCS#11, confirmación y PIN.
- `agent-distribution`: configuración, diagnóstico, instancia única, registro y empaquetado/instalación para Windows.

### Modified Capabilities

(ninguna: el servidor no cambia)

## Impact

- Código nuevo en `agent/` y pruebas en `agent/tests/`; una prueba de punta a punta en `tests/`.
- Dependencias del agente: `python-pkcs11`, `cryptography`; de empaquetado: `pyinstaller`. El servidor no cambia.
- CI: un workflow con SoftHSM para las pruebas PKCS#11.
- Documentación: `docs/agent-contract.md`, `agent/README.md` (instalación, política de Chrome `LocalNetworkAccessAllowedForUrls`, despliegue por política de dominio).
- Sin cambios de esquema ni de API del servidor.

## Fuera de alcance

- El widget que habla con el agente (FIRDOC-30) y el servidor de firma en lote (FIRDOC-22).
- Firma con claves no RSA (ECDSA) y con mecanismos distintos de `CKM_RSA_PKCS`.
- Instalador firmado digitalmente (code signing), actualización automática e icono en la bandeja del sistema.
- Soporte de macOS y Linux como plataforma de usuario (el agente es de Windows; el código es portable pero solo se prueba en Windows y, para SoftHSM, en Linux).
- Prueba con un token físico: queda como procedimiento manual documentado, a ejecutar cuando se disponga del dispositivo (el README indica un mToken CryptoID como token de referencia).
- Gestión desde el servidor de qué orígenes acepta el agente: el agente lee su propia configuración local.
