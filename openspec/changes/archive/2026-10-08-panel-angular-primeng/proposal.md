## Why

El panel de administración es una página estática (`admin_ui/index.html` + `admin.js`) que construye todo a mano con `createElement`. Sirvió para validar los flujos, pero cada pantalla nueva del mockup (FIRDOC-36 a 39) cuesta más en JavaScript crudo que en un framework, y el README promete un panel como aplicación de componentes. Además, es el ejemplo de referencia de cómo un sistema integrador (en la institución: aplicaciones Angular) embebe el widget: tener la carga de documentos y el iframe del widget resueltos en Angular es documentación ejecutable para quien integre.

Implementa **FIRDOC-47** (épica FIRDOC-4, panel y auditoría) y la HU del README «Panel de administración y auditoría»: *como administrador quiero consultar el historial de firmas y firmar documentos desde el panel*.

## What Changes

- **Nueva carpeta `frontend/`**: aplicación Angular 21 (standalone, zoneless) con PrimeNG 21, en español. Reproduce las secciones del panel estático vigente (FIRDOC-36 a 38): ingreso con token, menú lateral (`p-menu`) con Firmar documento, Documentos (listado con filtros, origen, versión y vencimiento, y detalle como cadena de custodia con línea de tiempo, versiones descargables y detalle técnico), Auditoría (webhooks y eventos), Integradores (alta, orígenes, rotación de claves, habilitar/deshabilitar, credenciales de un solo uso) y Confianza (anclas y certificado propio). Modo claro/oscuro con la misma regla (sigue al sistema hasta que la persona elige).
- **Carga de documentos con PrimeNG** (`p-fileupload`): uno o varios PDF, validación en el navegador (tipo y tamaño), lista de archivos con quitar, botón «Cargar y firmar». Después de cargar, tarjeta del documento (o lista del lote) y el **widget embebido en un `iframe`** con la `signing_url` devuelta, con `sandbox`, `allow` y `referrerpolicy` iguales a los del panel estático. Los mensajes `postMessage` del widget se aceptan solo si vienen de la ventana del iframe y del origen de la `signing_url`.
- **Backend**: sirve el build de Angular en `GET /panel` (y sus recursos) con la misma CSP estricta que `/admin`, más un **nonce por pedido** para los estilos que Angular y PrimeNG inyectan en tiempo de ejecución (`ngCspNonce`); `404` si la administración está deshabilitada o si el build no existe (`503` con `code: frontend_not_built`, como el widget). Nueva variable `FIRMADOC_FRONTEND_DIST`.
- **Origen del dev server**: nueva variable `FIRMADOC_PANEL_ORIGINS` (orígenes extra, separados por coma, por ejemplo `http://localhost:4200`) que se suman a `FIRMADOC_PUBLIC_BASE_URL` como `allowed_origins` del sistema interno «Firmadoc (panel)», para que el widget acepte ser enmarcado desde `ng serve`. Los orígenes del sistema interno se sincronizan con la configuración en cada carga.
- **Documentación y CI**: `README.md`, `docs/admin.md` y `frontend/README.md` explican cómo correr y compilar el panel; `ci.yml` suma el job `frontend` (instalar, probar, compilar).

## Fuera de alcance

- Reemplazar o borrar el panel estático de `/admin`: sigue sirviéndose igual (sus pruebas en Chrome y la propuesta `panel-origen-custodia-e-integradores` lo usan). Retirarlo es una decisión posterior.
- Pantallas que todavía no existen en el panel estático (FIRDOC-39): el panel Angular replica lo que hoy existe, con el mismo API.
- Enrutamiento con URL por sección, usuarios individuales, roles.
- Pruebas en Chrome real del panel Angular (quedan las unitarias de Angular y las de pytest del backend).

## Capabilities

### New Capabilities
- `angular-panel`: panel de administración como aplicación Angular + PrimeNG, su carga de documentos con el widget embebido, y cómo el servidor lo sirve.

### Modified Capabilities
- `pdf-upload-signing`: los orígenes permitidos del sistema interno del panel incluyen `FIRMADOC_PANEL_ORIGINS` y se mantienen sincronizados con la configuración.

## Impact

- Backend: `config.py` (`frontend_dist`, `panel_origins`), `services/panel_upload.py` (orígenes del sistema interno), nuevo `api/frontend_pages.py`, `main.py`.
- Nuevo `frontend/` (Angular + PrimeNG) con sus pruebas unitarias.
- `.env.example`, `README.md`, `docs/admin.md`, `.github/workflows/ci.yml`, `.gitignore`.
- Sin migraciones ni cambios en la API de administración.
