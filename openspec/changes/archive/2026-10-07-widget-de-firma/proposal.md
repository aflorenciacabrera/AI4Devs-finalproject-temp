## Why

El servidor y el agente local ya funcionan, pero la persona que firma no tiene dónde hacerlo: falta el **widget**, la interfaz que el sistema integrador embebe en su propia pantalla y que coordina al servidor con el agente (listar certificados del token → `prepare` → agente `/sign` → `complete`). Sin él el modo principal de Firmadoc solo se puede recorrer con scripts.

Hay además un problema de seguridad que el widget obliga a resolver: toda la API de firma exige la `X-API-Key` del sistema integrador, y **una clave de servidor no puede viajar al navegador del usuario**. El widget necesita una credencial propia, acotada a **una única solicitud de firma** y de corta vida, que el integrador reciba en la `signing_url` junto con la solicitud.

Backlog: FIRDOC-30 (widget React embebible), FIRDOC-11 (embeber vía iframe), FIRDOC-12 (elegir proveedor desde el widget; solo el proveedor de la solicitud, ver "Fuera de alcance"), FIRDOC-13 (confirmación con detalle del firmante y certificado).

## What Changes

- **Credencial del widget** (`widget-session`): la `signing_url` incluye un token firmado (HMAC), con vencimiento y atado a una sola solicitud, en el *fragmento* de la URL (`#t=...`) para que no llegue a registros ni al `Referer`. El token solo habilita los endpoints del widget; nunca los de integración.
- **Endpoints del widget** (`widget-session`): contexto de la solicitud, `prepare`, `complete` y descarga del PDF firmado, autenticados con ese token y reutilizando el flujo existente.
- **Entrega segura de la página** (`widget-session`): el servidor sirve el widget compilado en `/sign/{id}` con `Content-Security-Policy: frame-ancestors` igual a los orígenes permitidos del integrador de esa solicitud (evita clickjacking), y los recursos estáticos del widget.
- **El widget** (`signing-widget`): SPA React + TypeScript con las pantallas del mockup (detección del agente, elección del certificado, certificado rechazado antes del PIN, esperando la confirmación en el agente, firma completada con descarga) para los proveedores `token` y `local`, con estados de error claros, accesible por teclado y con lectores de pantalla.
- **Embebido** (`widget-embedding`): contrato de mensajes `postMessage` hacia la página que lo embebe (con `targetOrigin` explícito, nunca `*`), uso por `<iframe>`, un Web Component liviano `<firmadoc-widget>` que envuelve el iframe, una página anfitriona de ejemplo y una guía para Angular.
- Prueba **de punta a punta en un navegador real** (Chrome): página anfitriona → iframe → servidor + agente reales → firma verificada.
- `signing_url` pasa a incluir el token (`.../sign/{id}#t=...`).

## Capabilities

### New Capabilities

- `widget-session`: credencial acotada del widget, endpoints del widget y entrega segura de la página.
- `signing-widget`: comportamiento de la interfaz de firma (flujos, estados, errores, accesibilidad).
- `widget-embedding`: integración en la página anfitriona (iframe, Web Component, mensajes, guía Angular).

### Modified Capabilities

- `signature-requests`: la `signing_url` de la respuesta incluye el token del widget.

## Impact

- Servidor: nuevos módulos (token de firma, rutas del widget, entrega estática) y `config.py` (`FIRMADOC_SIGNING_SECRET`, `FIRMADOC_SIGNING_TOKEN_TTL_SECONDS`, `FIRMADOC_AGENT_URL`, `FIRMADOC_WIDGET_DIST`). Sin cambios de esquema.
- Cliente: `widget/` pasa de README a un proyecto Node (Vite, React, TypeScript, Vitest, Testing Library). Requiere Node 20+ para compilar; el servidor solo necesita los archivos compilados.
- Pruebas: Vitest para el widget y pytest (con Playwright y Chrome) para la prueba de punta a punta.
- CI: jobs de compilación y pruebas del widget y de punta a punta.
- Documentación: `widget/README.md`, guía de integración (iframe, Web Component, Angular) y ajuste del ejemplo de Web Component del README raíz (`signing-url` en lugar de `request-id`).

## Fuera de alcance

- **Elegir el método de firma desde el widget** ("Cambiar método" del mockup): el proveedor lo fija el integrador al crear la solicitud; cambiarlo requiere un cambio de API. El widget soporta `token` y `local`; para `firmar` (remoto) muestra que el método no está disponible.
- Firma en lote y listado de documentos pendientes (FIRDOC-22 y la grilla del mockup).
- Webhook al integrador (FIRDOC-24): el widget notifica por `postMessage`; la notificación servidor a servidor es otro change.
- Panel de administración, sello de tiempo (el mockup muestra B-LT; hoy las firmas son B-B y el widget muestra el nivel real que informa el servidor).
- App Angular real de prueba: se entrega una página anfitriona HTML más una guía de uso en Angular (criterio del README cubierto en la documentación, no con una app Angular).
- Modo de Web Component "in-page" sin iframe (CORS y aislamiento distintos): el Web Component de este change usa un iframe por dentro.
- Internacionalización: solo español (rioplatense).
- Tema oscuro y adaptación a la identidad visual de cada integrador.
