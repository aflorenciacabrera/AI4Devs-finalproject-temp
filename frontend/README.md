# Panel de Firmadoc (Angular + PrimeNG)

Panel de administración como aplicación Angular 21 (componentes standalone, sin zone.js, sin enrutador) con PrimeNG 21. Cubre lo mismo que el panel estático de `/admin`: ingreso con token, **Firmar documento** (carga de uno o varios PDF y widget de firma embebido), Documentos, Auditoría, Integradores y Confianza.

Se usa **PrimeNG 21** (licencia MIT) a propósito: desde la versión 22 PrimeNG pasó a la licencia «PrimeUI» (clave obligatoria, gratuita para estudiantes y equipos chicos, comercial para el resto) y sin clave muestra un aviso. Actualizar a 22+ implica decidir esa licencia.

Es también el ejemplo de referencia de cómo una aplicación Angular embebe el widget: `src/app/sections/widget-dialog.ts` (iframe en un `DynamicDialog` de PrimeNG, abierto desde `sign.ts`).

## Desarrollo

```
cd frontend
npm install
npm start           # http://localhost:4200/panel/
```

`ng serve` reenvía `/api` al backend en `http://127.0.0.1:8000` (`proxy.conf.json`). Para que el widget acepte ser enmarcado desde el servidor de desarrollo, el backend tiene que conocer ese origen:

```
FIRMADOC_PANEL_ORIGINS=http://localhost:4200
```

(se suma al de `FIRMADOC_PUBLIC_BASE_URL` como origen permitido del sistema interno «Firmadoc (panel)»; se actualiza en la siguiente carga de un PDF). El iframe carga la `signing_url` absoluta del backend y el panel solo acepta mensajes del widget que vengan de la ventana del iframe y de ese origen.

```
npm test            # pruebas unitarias (Vitest)
npm run build       # dist/firmadoc-panel/browser
```

## Producción: servido por el backend en `/panel`

El backend sirve el build en `GET /panel` (`FIRMADOC_FRONTEND_DIST`, por defecto `frontend/dist/firmadoc-panel/browser`) con la misma CSP estricta que `/admin`. Angular y PrimeNG inyectan estilos en tiempo de ejecución, así que el servidor genera un **nonce por pedido**, lo escribe en el atributo `ngCspNonce` de `<app-root>` (marcador `FIRMADOC_NONCE` en `index.html`) y lo declara en `style-src`. Por eso:

- el build se compila con `baseHref: /panel/` y sin CSS crítico en línea (`inlineCritical: false` en `angular.json`);
- `main.ts` lee el nonce y lo pasa a PrimeNG (`providePrimeNG({ csp: { nonce } })`).

Compartiendo origen con `FIRMADOC_PUBLIC_BASE_URL`, el widget se embebe sin configuración extra. Sin build, `/panel` responde `503` con `code: frontend_not_built`; sin token de administración, `404`.

## Estructura

```
src/app/
├── app.ts, app.html          # encabezado, menú lateral (p-menu), tema, toast y diálogo de confirmación
├── app.config.ts             # HttpClient, PrimeNG (tema Aura, modo oscuro por data-theme, nonce)
├── core/
│   ├── admin-api.ts          # cliente de /api/v1/admin: token en sessionStorage, Bearer, 401 cierra sesión
│   ├── api-types.ts          # tipos de las respuestas
│   ├── format.ts             # fechas, tamaños, etiquetas y pipes
│   └── theme.ts              # claro/oscuro
└── sections/
    ├── login.ts
    ├── sign.ts / sign.html   # p-fileupload con plantillas propias; abre el widget en un diálogo dinámico
    ├── widget-dialog.ts      # DynamicDialog con el iframe del widget y los mensajes validados por ventana y origen
    ├── documents.*           # listado con filtros y detalle (custodia, versiones, detalle técnico)
    ├── audit.*               # entregas de webhook y eventos
    ├── integrators.*         # alta, orígenes, rotación de claves, habilitar/deshabilitar
    └── trust.*               # anclas de confianza y certificado propio
```

Seguridad: no se usa `innerHTML`; el único `bypass` del sanitizador es el `src` del iframe, con una `signing_url` que entrega el propio backend. Las credenciales de un integrador se muestran una sola vez y nunca se guardan.
