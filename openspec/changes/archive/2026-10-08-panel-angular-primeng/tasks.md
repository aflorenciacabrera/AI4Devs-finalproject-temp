## 1. Backend

- [x] 1.1 `Settings`: `frontend_dist` y `panel_origins`; `.env.example`
- [x] 1.2 `panel_upload.get_panel_system`: orígenes = `public_base_url` + `panel_origins`, sincronizados en cada carga
- [x] 1.3 `api/frontend_pages.py`: `GET /panel` y `/panel/{archivo}` con CSP estricta, nonce por pedido en `ngCspNonce`, `404`/`503`; registrar en `main.py`
- [x] 1.4 Pruebas pytest: cabeceras y nonce, build ausente, administración deshabilitada, recorrido de rutas, orígenes extra y sincronización

## 2. Panel Angular (`frontend/`)

- [x] 2.1 Workspace Angular 21 (standalone, zoneless, sin enrutador) con PrimeNG 21 y tema Aura; `proxy.conf.json`; `inlineCritical` apagado; `base-href /panel/`; `ngCspNonce` en `index.html`
- [x] 2.2 `core/`: tipos del API, servicio de API (token en `sessionStorage`, Bearer, `401` cierra sesión), servicio de tema, formato de fechas y tamaños
- [x] 2.3 Ingreso, contenedor con menú lateral (`p-menu`), encabezado con tema y cerrar sesión, `p-toast` y `p-confirmdialog`
- [x] 2.4 Sección «Firmar documento»: `p-fileupload` (varios PDF, validación), carga individual o en lote, tarjeta/lista, pasos «Cómo se firma», iframe del widget y mensajes validados
- [x] 2.5 Secciones Documentos (filtros, paginación, detalle con línea de tiempo, versiones descargables y detalle técnico), Auditoría (webhooks con reenvío y eventos), Integradores (alta, orígenes, rotación de claves, habilitar/deshabilitar) y Confianza (anclas y certificado propio)
- [x] 2.6 Pruebas unitarias (Vitest): formato, servicio de API, filtro de mensajes del widget, validación de archivos
- [x] 2.7 `npm run build` y `npm test` sin errores

## 3. Documentación y cierre

- [x] 3.1 `frontend/README.md`, `README.md` y `docs/admin.md`: cómo correr (`ng serve` + `FIRMADOC_PANEL_ORIGINS`), compilar y servir en `/panel`
- [x] 3.2 `ci.yml`: job `frontend` (instalar, probar, compilar)
- [x] 3.3 `pytest` y `ruff check` sin errores
