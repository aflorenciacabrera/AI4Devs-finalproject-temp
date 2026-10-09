# Administración

## Habilitar

Definir `FIRMADOC_ADMIN_TOKEN` (mínimo 32 caracteres; generar con
`python -c "import secrets; print(secrets.token_urlsafe(32))"`). Sin él, toda la administración responde `404`.
El token es **distinto** de las API keys de integrador y no las reemplaza. Panel: `https://<servidor>/admin`.

Todas las rutas de la API usan `Authorization: Bearer <token>`.

## API (`/api/v1/admin`)

| Ruta | Para qué |
|---|---|
| `GET /signature-requests` | Historial con filtros `integrating_system_id`, `status`, `provider`, `signer` (CUIL exacto o texto del nombre), `created_from`, `created_to`, `limit` (≤ 200), `offset`; devuelve `total` |
| `GET /documents/{id}/custody` | Versiones, solicitudes con eventos, desafíos y entregas de webhook (sin hashes a firmar ni cuerpos) |
| `GET /webhook-deliveries` · `POST /webhook-deliveries/{id}/retry` | Entregas y reenvío de las fallidas |
| `GET/POST /trust-anchors` · `DELETE /trust-anchors/{huella}` | Anclas de confianza (PEM de una sola CA o certificado autofirmado vigente) |
| `GET /local-certificate` · `POST /local-certificate/rotate` | Certificado propio del proveedor `local` |
| `GET /events` | Acciones de administración registradas |

## Panel Angular (`/panel`)

Además del panel estático de `/admin`, `frontend/` contiene el mismo panel como aplicación **Angular 21 + PrimeNG 21**
(ver `frontend/README.md`). El backend lo sirve en `GET /panel` desde `FIRMADOC_FRONTEND_DIST` (por defecto
`frontend/dist/firmadoc-panel/browser`; se compila con `npm run build` en `frontend/`). Sin build responde `503`
(`code: frontend_not_built`); sin token de administración, `404`.

- Misma CSP que `/admin`, con `base-uri 'self'` (el build lleva `<base href="/panel/">`) y un **nonce por pedido** en
  `style-src` para los estilos que Angular y PrimeNG inyectan en tiempo de ejecución: el servidor lo escribe en el
  atributo `ngCspNonce` de `<app-root>`.
- En desarrollo (`ng serve` en `http://localhost:4200`), `FIRMADOC_PANEL_ORIGINS=http://localhost:4200` agrega ese
  origen a los permitidos del sistema interno «Firmadoc (panel)» (se sincronizan con la configuración en cada carga
  de un PDF), para que el widget acepte ser enmarcado desde ahí. Fuera de desarrollo se deja vacía.

## Qué queda registrado

Las acciones que **modifican** algo (reenviar un webhook, agregar/quitar un ancla, rotar el certificado) se
guardan en `admin_event`, una tabla append-only a nivel de base de datos (no admite `UPDATE` ni `DELETE`).
Las lecturas no se registran.

## Rotación del certificado propio

El certificado público vigente se archiva en `<FIRMADOC_LOCAL_CERT_DIR>/archive/` y la clave privada vieja
**se borra**. Las firmas anteriores siguen verificándose con `POST /documents/{id}/verify` porque el certificado
archivado se usa como ancla. Las firmas `local` que estaban preparadas pero sin completar durante la rotación
fallan y deben solicitarse de nuevo.

Limitación: tras un compromiso de la clave, una firma antigua no se puede distinguir de una forjada con la clave
robada hasta que exista sello de tiempo de una TSA (cambio de sello de tiempo).

## Anclas de confianza con varias réplicas

Agregar o quitar un ancla se aplica de inmediato en el proceso que atiende el pedido. Con varias réplicas todas
deben compartir el directorio `FIRMADOC_TRUST_DIR` (volumen compartido) y las demás lo toman al reiniciar.

## Seguridad del panel

CSP `script-src 'self'` sin scripts ni estilos en línea, `frame-ancestors 'none'`, `no-store`; el contenido se
construye siempre como texto; el token vive en `sessionStorage` (se borra al cerrar la pestaña) y no se usan
cookies. Un único token compartido no distingue personas: la identidad individual queda para una integración
con el directorio institucional. Limitar intentos de acceso por IP corresponde al proxy inverso.

## Firmar documento (carga de un PDF desde el panel)

La sección inicial del panel permite subir un PDF y firmarlo con el widget embebido, sin pasar por la API de un
integrador. El navegador envía `POST /api/v1/admin/signing-uploads` (token de administración) con
`{"filename", "document_base64", "signer"?}` y recibe `request_id`, `document_id`, `signing_url`, `filename`,
`page_count`, `size_bytes` y `document_hash`. Se aplican las mismas validaciones y el mismo tamaño máximo
(`FIRMADOC_MAX_DOCUMENT_BYTES`) que en la API de integradores.

- El documento pertenece al sistema interno **«Firmadoc (panel)»**, creado la primera vez; su único origen permitido
  es el de `FIRMADOC_PUBLIC_BASE_URL` y su API key se descarta (no sirve en la API de integradores). El nombre
  está reservado: `integrators create` lo rechaza. **Abrir el panel por el mismo origen que `PUBLIC_BASE_URL`**
  (por ejemplo, no `127.0.0.1` si está configurado `localhost`) o el navegador no podrá embeber el widget.
- Sin `signer`, el firmante registrado es «Operador del panel»; la firma refleja el sujeto del certificado usado.
- El método inicial es el primero habilitado entre `token`, `firmar` y `local`, y el widget ofrece todos los
  habilitados (en modo real, sin `local`).
- Cada carga queda en `admin_event` (`panel_upload`: documento, solicitud, nombre de archivo y hash, sin contenido).
- La sección acepta un solo PDF (el lote desde el panel es otro cambio). «Quitar» o «Reemplazar» no borra lo ya
  cargado: las versiones son append-only y la solicitud queda pendiente en el listado.

### Varios PDF: lote desde el panel

La misma sección acepta varios PDF. Con más de uno arma una lista (se puede quitar alguno) y, al confirmar, envía
`POST /api/v1/admin/signing-batch-uploads` con `{"documents": [{"filename", "document_base64"}, …], "signer"?}`
(de 2 a `FIRMADOC_MAX_BATCH_SIZE`; es atómico: si uno es inválido no se crea nada, `422`). El lote queda en el sistema
interno del panel con los métodos `token` y `local` según estén habilitados (sin firma remota) y se firma con el widget
de lote embebido. Responde `201` con `batch_id`, `signing_url` y, por documento, `document_id`, `filename`, `page_count`,
`size_bytes` y `document_hash`. Queda un evento `panel_batch_upload` en `admin_event` (sin contenido). Los documentos
cargados desde el panel se muestran en el widget con el nombre del archivo.

## Navegación y vistas del panel

La barra lateral tiene cinco secciones: **Firmar documento**, **Documentos**, **Auditoría** (entregas de webhook y
eventos de administración), **Integradores** y **Confianza** (anclas de confianza y certificado propio).

### Documentos

Columnas: Documento (con `vN`), Firmante, Fecha, Proveedor, **Origen** («Individual» o «Lote #xxxxxxxx», los primeros
8 caracteres del id del lote; las filas de un lote van juntas, ordenadas por la fecha del lote), Estado (Firmado,
Pendiente con su **vencimiento**, Firmando, Fallido) y Acciones. Filtros: búsqueda `q` por nombre o id externo del
documento o por firmante, estado, proveedor, `origin` (`individual` | `batch`) y fechas. Equivalente por API:
`GET /api/v1/admin/signature-requests?origin=batch&q=…` (agrega `origin` y `document.signature_deadline` a cada ítem).

### Detalle del documento (cadena de custodia)

`GET /api/v1/admin/documents/{id}/custody` agrega `timeline` (entradas `{at, actor, title, detail, kind}` ordenadas por
hora, armadas con los eventos de auditoría y las entregas de webhook: solicitud creada, método elegido, desafío
preparado, firma recibida del agente, firma incrustada, nueva versión registrada, certificado rechazado, firma fallida,
sello de tiempo no disponible, webhook entregado o fallido) y `technical` (ID de transacción, proveedor, nivel de firma,
certificado, emisor y serie, firmante, hash original y hash del firmado vigente). Los datos originales (`events`,
`challenges`, `webhook_deliveries`) se conservan. **No hay «IP de origen»**: el sistema no la registra.

`GET /api/v1/admin/documents/{id}/versions/{n}/download` devuelve el PDF de esa versión (v1 original sin firma, v2 firmada)
con el token de administración y `Cache-Control: no-store`; la interfaz lo baja con `fetch` y el token en `Authorization`.

### Integradores

Bajo `/api/v1/admin/integrators` (token de administración): `GET` (lista), `POST` (crea), `PATCH /{id}` (orígenes
permitidos), `POST /{id}/rotate-webhook-secret`, `POST /{id}/rotate-api-key`, `POST /{id}/disable` y `/enable`.

- La **API key y el secreto de webhook en claro se devuelven solo al crear y al rotar**; de la API key solo se guarda el
  hash. La interfaz los muestra una vez, con «Copiar», y no los guarda en el navegador.
- Un integrador **deshabilitado** no puede usar la API (mismo `401` que una clave inválida); los enlaces del widget que ya
  emitió siguen sirviendo hasta vencer, para que las firmas en curso terminen. Un integrador no se borra: deja historia.
- El sistema interno «Firmadoc (panel)» figura como interno y no se modifica (`409`).
- Cada acción queda en `admin_event` (`integrator_created`, `integrator_origins_changed`,
  `integrator_webhook_secret_rotated`, `integrator_api_key_rotated`, `integrator_disabled`, `integrator_enabled`) sin
  secretos. Rotar la API key deja sin acceso al integrador hasta que use la nueva.
