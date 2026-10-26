## 1. Sistema integrador interno (FIRDOC-44)

- [x] 1.1 Agregar `get_panel_system(db, settings)` que busca o crea «Firmadoc (panel)» con origen = origen de `public_base_url`, API key aleatoria descartada y secreto de webhook aleatorio
- [x] 1.2 Rechazar el nombre reservado «Firmadoc (panel)» en `integrators.create` (CLI y API) con mensaje claro
- [x] 1.3 Tests: creación diferida e idempotente, origen permitido correcto, ninguna API key autentica contra el sistema (401), el alta de integradores rechaza el nombre reservado

## 2. Servicio y endpoint de carga (FIRDOC-44)

- [x] 2.1 Crear `services/panel_upload.py`: elegir proveedor inicial (token, firmar, local), llamar a `flow.create_request` con firmante por defecto «Operador del panel» y `allowed_providers` = habilitados
- [x] 2.2 Extraer metadatos de la carga (páginas con el motor PDF existente, tamaño, hash de la versión v1, nombre de archivo saneado) y devolverlos junto con `signing_url`
- [x] 2.3 Registrar el `AuditEvent` de administración de la carga (documento, nombre de archivo, hash; sin contenido)
- [x] 2.4 Agregar `POST /api/v1/admin/signing-uploads` con esquemas Pydantic (`filename` obligatorio y acotado, `document_base64`, `signer` opcional) bajo `admin_auth`
- [x] 2.5 Tests de API: carga válida (201, v1 de origen subido, solicitud pendiente, URL del widget), base64 inválido, no-PDF, exceso de tamaño sin dejar filas, sin token (401), administración deshabilitada (404), firmante por defecto, modo real sin `local`
- [x] 2.6 Test de seguridad: el evento de auditoría no contiene el PDF y el listado de eventos de administración lo muestra

## 3. Embebido del widget por el propio servidor (FIRDOC-44)

- [x] 3.1 Test de `/sign/{id}` para una solicitud del panel: `frame-ancestors` contiene el origen del servidor
- [x] 3.2 Test de `/sign/{id}` para una solicitud de otro integrador: `frame-ancestors` no contiene el origen del servidor
- [x] 3.3 Completar la firma de una solicitud del panel con el proveedor `local` por la API del widget (prueba de integración del flujo de punta a punta, versión firmada = v2 vigente)

## 4. Página del panel: CSP y estructura (FIRDOC-45)

- [x] 4.1 Añadir `frame-src 'self'` a la CSP de `admin_pages.py` manteniendo `frame-ancestors 'none'`; actualizar el test de cabeceras
- [x] 4.2 Agregar la pestaña «Firmar documento» en `admin_ui/index.html` con la zona de carga, la tarjeta del documento, los pasos «Cómo se firma» y el contenedor del widget, sin scripts ni estilos en línea
- [x] 4.3 Estilos en `admin.css` según el mockup `SignUpload`/`SignUploadReady` (zona punteada, tarjeta, pasos numerados, marco del widget)

## 5. Lógica de la sección (FIRDOC-45)

- [x] 5.1 En `admin.js`: selección y arrastrar-soltar de un solo archivo, rechazo en el navegador de tipos que no sean PDF y de tamaños excesivos, con mensajes por `textContent`
- [x] 5.2 Lectura a base64, llamada a `POST /api/v1/admin/signing-uploads` con el token, y render de la tarjeta (nombre, páginas, tamaño, aviso v1/v2) con «Reemplazar» y «Quitar»
- [x] 5.3 Crear el iframe del widget con la `signing_url`, `sandbox`, `allow` de red local y `referrerpolicy="no-referrer"`
- [x] 5.4 Escuchar `firmadoc:signed|failed|cancelled` validando `origin` y `source`, mostrar el resultado y permitir cargar otro documento; revisar la pantalla de éxito del widget para no duplicar la descarga
- [x] 5.5 Test de seguridad en navegador (prueba existente en Chrome real o jsdom): un nombre de archivo con HTML se muestra como texto y un `postMessage` de otro origen se ignora

## 6. Verificación y documentación

- [x] 6.1 Probar en Chrome real el flujo completo: cargar PDF, elegir «Firma propia», firmar y comprobar v2 vigente y evento de auditoría en custodia
- [x] 6.2 Documentar el endpoint y la sección en `docs/admin.md` y enlazar desde `docs/documents-api.md`
- [x] 6.3 Ejecutar la suite completa de pruebas y el linter y corregir regresiones
- [x] 6.4 Pasar FIRDOC-44 y FIRDOC-45 a Listo en Jira al cerrar el change
