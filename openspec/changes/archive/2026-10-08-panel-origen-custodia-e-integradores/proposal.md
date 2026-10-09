## Why

El panel de administración funciona (FIRDOC-14, 15, 27) pero es una serie de pestañas con tablas crudas, distinto del mockup (`AdminList`, `AdminDetail` y el menú con «Integradores»). Un administrador no distingue si un documento se firmó solo o en lote, no ve el vencimiento de los pendientes, lee la custodia como filas técnicas en vez de una historia, y para dar de alta un sistema integrador tiene que usar la línea de comandos aunque el README diga que lo hace el panel.

Implementa **FIRDOC-36** (listado con Origen, versión y vencimiento), **FIRDOC-37** (detalle como cadena de custodia con línea de tiempo, versiones y datos técnicos) y **FIRDOC-38** (gestión de integradores y claves de API), todos de la épica de panel y auditoría (FIRDOC-4), según las HU del README de panel, auditoría e integradores.

## What Changes

- **Navegación y estilo del mockup**: barra lateral con Firmar documento, Documentos, Auditoría, Integradores y Confianza, reemplazando las pestañas; Auditoría reúne webhooks y eventos de administración y Confianza reúne las anclas y el certificado propio.
- **Listado «Documentos» (FIRDOC-36)**: columnas Documento (con `vN`), Firmante, Fecha, Proveedor, **Origen** («Individual» o «Lote #xxxx», con las filas de un lote juntas), Estado en español con color y **vencimiento** de los pendientes; filtros por estado, proveedor, origen y fechas; búsqueda por documento o firmante.
- **Detalle del documento (FIRDOC-37)**: «Volver a Documentos», encabezado con estado y descarga del firmado, **línea de tiempo** legible con hora y actor, tarjeta **Versiones** con descarga de cada una (nuevo endpoint de descarga de administración) y **Detalle técnico** (ID de transacción, proveedor, nivel PAdES, certificado y emisor, hash original y firmado, firmante).
- **Integradores (FIRDOC-38)**: nueva pantalla para listar, crear (API key y secreto de webhook se muestran una sola vez), editar orígenes permitidos, rotar el secreto de webhook, rotar la API key y deshabilitar o habilitar un integrador (migración aditiva `disabled_at`); cada acción queda en `admin_event`. El sistema interno del panel figura como «interno» y no se puede modificar.
- **API de administración**: `GET /signature-requests` agrega `origen`, `vencimiento` y filtros; `GET /documents/{id}/custody` agrega la línea de tiempo y el detalle técnico; nuevos endpoints de integradores y de descarga de versiones.

## Capabilities

### New Capabilities
<!-- Ninguna: se extienden las capacidades de panel, vistas de auditoría e integradores. -->

### Modified Capabilities
- `admin-audit-views`: columnas Origen/versión/vencimiento y filtros del listado; línea de tiempo, versiones con descarga y detalle técnico de la custodia.
- `admin-panel`: navegación lateral y estilo del mockup, pantalla de Integradores.
- `integrator-management`: alta, edición, rotación de claves y deshabilitación desde la API de administración y su auditoría.

## Impact

- Código: `services/admin.py` (listado y custodia), nuevo `services/integrator_admin.py`, `api/admin_routes.py`, `api/deps.py` (integrador deshabilitado), `integrators.py`, `models.py`, migración `0008`, `admin_ui/` (index.html, admin.js, admin.css).
- API: campos y filtros nuevos opcionales en endpoints existentes; endpoints nuevos bajo `/api/v1/admin`. Migración aditiva (columna nullable), no destructiva.
- Docs: `docs/admin.md`.
- Dependencias: ninguna.

## Fuera de alcance

- **«IP de origen»** del mockup: el backend no la registra. Se omite del detalle técnico y se deja anotado; quitarla del mockup o agregar el registro es otra decisión (FIRDOC-39 actualiza el mockup).
- Pantallas del mockup que faltan en el panel (FIRDOC-39) y el README (FIRDOC-40).
- Roles o identidad individual de administradores (un único token compartido, como hoy).
- Eliminar integradores (se deshabilitan; hay documentos y auditoría que dependen de ellos) y exportar el listado.
- Búsqueda por ID de documento en una caja aparte: se llega al detalle desde el listado.
