## Context

- El panel estático (`admin_ui/`) se sirve con CSP `script-src 'self'; style-src 'self'` y sin estilos en línea. Angular y PrimeNG inyectan `<style>` en tiempo de ejecución (estilos de componentes y el tema de PrimeNG), que esa CSP bloquea salvo con un nonce.
- La `signing_url` es absoluta (`FIRMADOC_PUBLIC_BASE_URL/sign/{id}#t=…`) y la página del widget responde `frame-ancestors` con los `allowed_origins` del sistema de la solicitud. El sistema interno «Firmadoc (panel)» se crea una vez con el origen de `PUBLIC_BASE_URL` y no se actualiza.
- El widget envía `postMessage` a cada origen permitido (nunca `*`); la página anfitriona valida ventana y origen.
- Angular CLI 21 compila a `dist/<proyecto>/browser/` con `index.html` y recursos con hash; por defecto incrusta el CSS crítico en línea (`inlineCritical`).

## Goals / Non-Goals

**Goals:** un panel Angular + PrimeNG liviano (sin NgModules, sin zone.js, sin enrutador) que cubra lo mismo que el estático, con la carga de documentos y el widget embebido como ejemplo de integración; servirlo desde el backend sin aflojar la CSP; que funcione también con `ng serve` contra el backend local.

**Non-Goals:** retirar `/admin`; nuevas pantallas; pruebas en Chrome real del panel Angular.

## Decisions

1. **Servido por el backend en `/panel`** (`api/frontend_pages.py`), no en un servidor aparte. Así en producción el panel comparte origen con `PUBLIC_BASE_URL` y el iframe del widget funciona sin configuración extra. Rutas: `GET /panel` sirve `index.html`; `GET /panel/{archivo}` sirve solo archivos que existen dentro del build (sin salir del directorio, sin `index.html` de respaldo porque no hay enrutador). Build compilado con `--base-href /panel/`.
2. **CSP con nonce por pedido**: la cabecera es la del panel estático más `'nonce-<aleatorio>'` en `style-src`; el `index.html` del build lleva el marcador `ngCspNonce="FIRMADOC_NONCE"` en `<app-root>`, que el servidor reemplaza al servirlo. Angular aplica el nonce a sus estilos y la app lo pasa a PrimeNG (`providePrimeNG({ csp: { nonce } })`). Se desactiva `inlineCritical` en `angular.json` para que el build no incruste `<style>` sin nonce. `script-src` se mantiene en `'self'` (los scripts del build son externos). Única diferencia con la CSP de `/admin`: `base-uri 'self'` en lugar de `'none'`, porque el build lleva `<base href="/panel/">` (verificado en Chrome: con `'none'` el navegador bloquea la base y no carga los recursos). Alternativa descartada: `style-src 'unsafe-inline'` (más simple, pero afloja la política del panel).
3. **`FIRMADOC_PANEL_ORIGINS`** (orígenes extra, coma) para el dev server. `get_panel_system` compone `allowed_origins = PUBLIC_BASE_URL + PANEL_ORIGINS` y lo **sincroniza** si difiere del guardado, para que un cambio de configuración surta efecto sin tocar la base. Fuera de desarrollo se deja vacía. En `ng serve` el panel llama a `/api` por el proxy (`proxy.conf.json`) y el iframe carga la `signing_url` absoluta del backend: `frame-ancestors` incluye `http://localhost:4200` y el widget le envía sus mensajes a ese origen.
4. **Estructura mínima de Angular**: `core/` (servicio de API con token en `sessionStorage` y señal de sesión, servicio de tema, formato), un componente por sección en `sections/` (Firmar, Documentos, Auditoría, Integradores, Confianza), y `app.ts` como contenedor con el menú lateral (`p-menu` con `MenuItem[]`, ítem activo por `styleClass`). Estado con señales; sin enrutador ni NgRx. Tipos de las respuestas del API en `core/api-types.ts`.
5. **PrimeNG**: tema Aura con `darkModeSelector: '[data-theme="dark"]'` para reusar la lógica de tema del panel estático (atributo `data-theme`, `localStorage`). Componentes: `p-fileupload` (modo avanzado, `customUpload`, varios archivos) para la carga, `p-table` para listados, `p-select`/`pInputText`/`pTextarea` para filtros y formularios, `p-toast` para mensajes, `p-confirmdialog` en lugar de `window.confirm`, `p-message` para el resultado de la firma.
6. **Seguridad del contenido**: Angular escapa las interpolaciones; no se usa `innerHTML` ni `bypassSecurityTrustHtml`. El único `bypass` es `bypassSecurityTrustResourceUrl` para el `src` del iframe, con una `signing_url` que entrega el propio backend. El `token` solo vive en memoria y en `sessionStorage`; `401` cierra la sesión.
7. **Iframe del widget**: mismos atributos que el panel estático (`sandbox="allow-scripts allow-same-origin allow-downloads"`, `allow="local-network-access; local-network; loopback-network"`, `referrerpolicy="no-referrer"`). El componente escucha `window:message` y acepta solo `event.source === iframe.contentWindow` y `event.origin === new URL(signing_url).origin`.
8. **Pruebas**: Angular con Vitest (el runner por defecto del CLI 21) para el formato, el servicio de API (Bearer, `401` → cierre de sesión) y el filtro de mensajes del widget; pytest para `/panel` (cabeceras, nonce, `404`/`503`, recorrido de rutas) y la sincronización de orígenes.

9. **Angular 21 + PrimeNG 21 (MIT), no PrimeNG 22.** PrimeNG 22 pasó a la «PrimeUI License» (comercial; gratuita para estudiantes y proyectos pequeños pero con clave obligatoria y renovación anual) y sin clave muestra un aviso «Invalid PrimeUI License». PrimeNG 21.1.x sigue bajo MIT y exige Angular 21, que es la versión LTS vigente. Así el repositorio no depende de una clave de licencia; se verificó en Chrome que PrimeNG 22 inyecta además un elemento con `style` en línea que la CSP bloquea.

## Risks / Trade-offs

- [Dos paneles conviven] → se documenta que `/admin` es el estático y `/panel` el Angular; retirar uno es una decisión posterior.
- [`inlineCritical` apagado] → una primera pintura algo más lenta; irrelevante para un panel interno.
- [PrimeNG podría inyectar estilos sin respetar el nonce en alguna versión] → se verifica en el navegador con la CSP activa; si fallara, el fallback documentado es `style-src 'unsafe-inline'` solo en `/panel`.
- [Node 22 en CI vs Node 24 local] → Angular 21 admite ambos; `package-lock.json` fija versiones.
- [Actualizar a PrimeNG 22+ en el futuro] → requiere decidir sobre la licencia PrimeUI (clave Community gratuita o comercial).

## Open Questions

- Ninguna que cambie el alcance.
