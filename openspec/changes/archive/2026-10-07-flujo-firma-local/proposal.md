## Why

Con el esquema de datos listo, falta el flujo de firma en sí. El proveedor `local` (certificado autofirmado, firma electrónica) permite recorrer `create` → `prepare` → `complete` de punta a punta sin token ni hardware, y es el camino que habilita la demo y los tests de la firma con token que vendrá después. Además fija el contrato del flujo diferido (hash que se firma / firma que se incrusta) sobre el que se apoyará el proveedor `token`.

Backlog: FIRDOC-23 (HU1, crear solicitud), FIRDOC-29 (backend firma diferida), FIRDOC-6 (HU5, motor propio), FIRDOC-8 (hash SHA-256 por versión).

## What Changes

- Autenticación de sistemas integradores por API key (`X-API-Key`, comparada contra `api_key_hash`).
- `POST /api/v1/signature-requests`: crea o reutiliza un `Document`, guarda la versión `uploaded` y devuelve `signing_url`.
- `POST /api/v1/signature-requests/{id}/prepare`: prepara la firma (firma interrumpida de pyHanko), crea un `SigningChallenge` de un solo uso con vencimiento y devuelve el hash a firmar.
- `POST /api/v1/signature-requests/{id}/complete`: verifica el desafío, incrusta la firma PAdES, crea la nueva `DocumentVersion` `signed` vigente y deja el documento descargable.
- `GET /api/v1/signature-requests/{id}` y descarga de una versión (`/api/v1/documents/{id}/versions/{n}/download`).
- Proveedor `local`: certificado autofirmado de demostración; el servidor firma el hash que prepara.
- Almacenamiento de binarios en el sistema de archivos local detrás de una interfaz (`storage_ref`).
- Eventos de auditoría `created`, `prepared`, `signed`, `failed`.
- Estado de solicitud y de documento actualizado de forma consistente (`pending → signing → signed|failed`, `signing_status`).

## Capabilities

### New Capabilities

- `signature-requests`: contrato de la API del flujo de firma diferida, autenticación del integrador, estados, versionado y descarga.
- `local-signing-provider`: proveedor `local` (firma electrónica de demostración con certificado autofirmado) y la interfaz común de proveedor que compartirán todos.
- `document-storage`: almacenamiento de binarios de versiones y su hash.

### Modified Capabilities

(ninguna: el esquema de `data-model` no cambia)

## Impact

- Código nuevo en `backend/src/firmadoc/` (API, servicios, proveedores, storage) y tests.
- Dependencias nuevas: `pyhanko`, `pyhanko-certvalidator`, `cryptography`.
- Variables de entorno nuevas: `FIRMADOC_STORAGE_DIR`, `FIRMADOC_LOCAL_CERT_DIR`, `FIRMADOC_PUBLIC_BASE_URL`, `FIRMADOC_CHALLENGE_TTL_SECONDS`, `FIRMADOC_MAX_DOCUMENT_BYTES`.
- Sin cambios de esquema ni de migraciones.

## Fuera de alcance

- Proveedor `token` y agente local; validación de cadena de confianza, revocación y CUIL de certificados de terceros (FIRDOC-20, FIRDOC-21).
- Sello de tiempo y niveles B-T/B-LT (FIRDOC-7): las firmas del proveedor `local` son B-B.
- Webhooks hacia el integrador (FIRDOC-24) y firma en lote (FIRDOC-22).
- Widget (FIRDOC-30), panel de administración y verificación de documentos (`/verify`).
- Estados `draft` / `pending_signature` con fecha límite (FIRDOC-25).
- Proveedor `firmar` (FIRDOC-9, FIRDOC-10).
