## Context

- La API de integradores ya crea documento + versión v1 + solicitud con `flow.create_request(ctx, document_base64=..., ...)`, y `flow.signing_url(ctx, request)` arma la URL del widget con el token en el fragmento. El widget se sirve en `/sign/{id}` con `frame-ancestors` calculado desde `IntegratingSystem.allowed_origins`.
- El panel (`/admin`) es una página de estáticos propios (HTML/JS/CSS sin dependencias) con CSP estricta, token de administración en `sessionStorage` y `frame-ancestors 'none'`. La API de administración usa `admin_auth` (Bearer), no API keys.
- `Ctx` exige un `IntegratingSystem`; las rutas de administración hoy no tienen uno. El panel React previsto en el README (`admin-panel/`) no existe; el panel real es `backend/src/firmadoc/admin_ui`.
- No se agrega `python-multipart`: toda la API usa JSON y `document_base64`.

## Goals / Non-Goals

**Goals:**
- Subir un PDF desde el navegador y firmarlo con el widget sin salir del panel, reutilizando el flujo de firma diferida existente.
- Mantener las garantías vigentes: validación del PDF, v1 inmutable, auditoría, CSP estricta, widget solo embebible desde orígenes permitidos.

**Non-Goals:**
- Lote desde el panel (FIRDOC-34), rediseño del selector de método del widget (FIRDOC-35), renderizado de páginas del PDF, múltiples operadores/roles.

## Decisions

1. **Endpoint de administración con JSON base64** (`POST /api/v1/admin/signing-uploads`), no multipart. Mantiene una sola convención de transporte y evita una dependencia; el costo (~33 % más de peso, límite de 20 MB) es aceptable. El navegador lee el archivo con `FileReader.readAsDataURL` y quita el prefijo.
2. **Sistema integrador interno «Firmadoc (panel)»**, creado de forma diferida por una función `get_panel_system(db, settings)`. Se busca por nombre reservado; si falta se crea con `allowed_origins = origen de public_base_url`, API key aleatoria cuyo valor en claro se descarta (solo se guarda el hash) y secreto de webhook aleatorio sin `callback_url`. Alternativa descartada: permitir `Ctx` sin sistema o sembrar el sistema por migración; ambas tocan más código/esquema. Consecuencia: el nombre queda reservado y `integrators.create` debe rechazar «Firmadoc (panel)» para que nadie lo suplante.
3. **Reutilizar `flow.create_request`** con un `Ctx` armado para el sistema interno. El servicio nuevo (`services/panel_upload.py`) solo: obtiene el sistema, elige el proveedor inicial, llama a `create_request`, extrae metadatos (páginas con el motor PDF existente, tamaño, hash de la versión creada) y registra el `AuditEvent` de administración.
4. **Proveedor inicial = primero habilitado en el orden token, firmar, local**, con `allowed_providers` = todos los habilitados, para que el selector actual del widget funcione. Reutiliza `get_provider`/disponibilidad ya usados por `services/widget.available_providers`.
5. **Firmante por defecto «Operador del panel»** con identificador `panel` y correo `panel@invalid`, porque el mockup no pide datos del firmante y la firma real toma el sujeto del certificado. Los campos opcionales de `signer` permiten usarlo con datos reales sin cambiar contrato.
6. **Embebido por iframe, no Web Component**: el panel ya impone `script-src 'self'` y el Web Component requiere cargar `widget.js` (también del mismo origen, pero acopla el panel al build del widget). El iframe aísla el widget y usa la página `/sign/{id}` existente. CSP del panel: añadir solo `frame-src 'self'`. `sandbox="allow-scripts allow-same-origin allow-downloads"` y el atributo `allow` de acceso a red local igual que `widget/examples/host.js`.
7. **Mensajes del widget**: se consume el mismo protocolo `firmadoc:*` que documenta el widget, validando `event.origin === location.origin` y `event.source === iframe.contentWindow`. La descarga del firmado se pide con la API existente del widget dentro del iframe; el panel solo informa el resultado y, si la descarga está disponible por `GET /api/v1/admin/...`, enlaza; si no, remite al botón de descarga del propio widget (ver Preguntas abiertas).
8. **Quitar/Reemplazar no borra en servidor**: las versiones son append-only y la solicitud queda `pending`. Es coherente con la inmutabilidad; el costo es documentos huérfanos sin firmar, visibles en el listado de solicitudes del panel.

## Risks / Trade-offs

- [Cargas huérfanas por «Quitar»/«Reemplazar»] → quedan como solicitudes pendientes visibles; expiración/limpieza queda fuera de alcance y se anota en docs.
- [Un token de administración permite crear solicitudes de firma] → mismo nivel de confianza que el resto del panel; el token ya da acceso a custodia y anclas. El endpoint registra auditoría.
- [Suplantación del nombre reservado del sistema interno] → rechazo del nombre en el alta de integradores (decisión 2) con test.
- [El widget necesita acceso al agente local desde un iframe] → mismo atributo `allow` y misma CSP `connect-src` del agente que ya usa la página `/sign`; se prueba con la prueba de punta a punta existente.
- [Base64 de 20 MB en un JSON] → el servidor rechaza por tamaño decodificado; el navegador valida el tamaño antes de enviar.

## Open Questions

- Descarga del PDF firmado desde la sección: si el widget ya la ofrece en su pantalla de éxito (`Success.tsx` con `download.ts`), alcanza con mostrar el resultado y no duplicar el botón; la tarea 5.4 lo verifica leyendo el widget antes de decidir. No cambia el alcance ni los endpoints.
