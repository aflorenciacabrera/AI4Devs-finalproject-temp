## Why

Hoy un PDF solo puede entrar a Firmadoc por la API de un sistema integrador (`document_base64` con API key). El mockup del producto (pantallas `SignUpload` y `SignUploadReady`) define que la firma **parte de cargar un PDF** en una sección «Firmar documento» del panel y se completa con el widget embebido en esa misma página. Esa sección no existe: la persona que administra no puede subir un PDF desde el navegador ni firmarlo, y la demostración de punta a punta depende de scripts.

Implementa **FIRDOC-44** (backend: cargar un PDF desde el navegador y crear la solicitud de firma) y **FIRDOC-45** (frontend: sección «Firmar documento»), dentro de la épica FIRDOC-33. Corresponde a la HU del README «se firma a partir de subir un PDF» (FIRDOC-40 alinea el texto del README después).

## What Changes

- **Backend (FIRDOC-44)**: nuevo endpoint de administración `POST /api/v1/admin/signing-uploads` que recibe un PDF (base64 en JSON, nombre de archivo y firmante opcional), lo valida con el mismo motor que la API de integradores, lo guarda como versión original v1 y crea la solicitud de firma, devolviendo la `signing_url` del widget, el identificador del documento y los metadatos de vista previa (nombre, páginas, tamaño, hash).
- **Sistema integrador interno**: los PDF cargados desde el panel pertenecen a un sistema integrador reservado «Firmadoc (panel)», creado la primera vez que se usa, cuyo único origen permitido para embeber el widget es el origen del propio servidor y sin API key utilizable.
- **Frontend (FIRDOC-45)**: sección «Firmar documento» en el panel (`/admin`): zona para soltar o seleccionar un PDF, tarjeta del documento cargado (nombre, páginas, tamaño, «Reemplazar», «Quitar», aviso de que se guarda como v1 y la firmada será v2), pasos «Cómo se firma» y el widget embebido por iframe con el selector de método, más el resultado final con descarga del firmado.
- **Seguridad de la página**: la CSP del panel pasa de no permitir frames a permitir solo `frame-src 'self'`; la página sigue sin poder ser embebida.
- Se escuchan los mensajes `firmadoc:signed`/`failed`/`cancelled` del widget validando origen y ventana.

## Capabilities

### New Capabilities
- `pdf-upload-signing`: carga de un PDF desde el panel y creación de la solicitud de firma lista para el widget (endpoint, sistema interno, validaciones y auditoría).

### Modified Capabilities
- `admin-panel`: nueva sección «Firmar documento» con vista previa del documento cargado y widget embebido, y ajuste de la CSP para permitir el iframe propio.
- `widget-embedding`: el origen del propio servidor puede embeber el widget cuando la solicitud pertenece al sistema interno del panel.

## Impact

- Código: `backend/src/firmadoc/api/admin_routes.py`, `services/` (nuevo servicio de carga), sistema interno (servicio o `integrators.py`), `api/admin_pages.py` (CSP), `admin_ui/index.html|admin.js|admin.css`.
- API: un endpoint nuevo bajo `/api/v1/admin` (token de administración). Sin cambios de contrato en la API de integradores ni migraciones de esquema (reutiliza `IntegratingSystem`, `Document`, `DocumentVersion`, `SignatureRequest`).
- Docs: `docs/admin.md` y `docs/documents-api.md` (referencia cruzada).
- Dependencias: ninguna nueva.

## Fuera de alcance

- Carga y firma de **varios** PDF en lote desde el panel (pantallas `MainBatch`, `AgentDialogBatch`, `BatchSuccess`): FIRDOC-34. La zona de carga acepta un solo archivo en este change.
- Selección de método y tarjeta de documento dentro del widget según el mockup: FIRDOC-35 (aquí se usa el selector actual del widget).
- Nuevas columnas y detalle de custodia en el panel: FIRDOC-36 y 37. Gestión de integradores y claves: FIRDOC-38.
- Autenticación de personas finales distinta del token de administración, y vista previa renderizada de las páginas del PDF (solo se muestran metadatos).
- Actualizar el README: FIRDOC-40.
