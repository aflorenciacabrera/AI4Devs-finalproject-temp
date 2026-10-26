## 1. Contexto del widget y métodos del lote en el servidor (FIRDOC-34, 35)

- [x] 1.1 Crear un helper compartido que lee la versión vigente y devuelve `page_count` y `size_bytes`; usarlo en la carga del panel
- [x] 1.2 Agregar `signing_status`, `signature_deadline`, `page_count` y `size_bytes` a `WidgetContext` y a `widget_context`, sin binarios
- [x] 1.3 Migración `0007`: `signature_batch.allowed_providers` (nullable, aditiva, con downgrade compatible con SQLite) y campo en el modelo
- [x] 1.4 `create_batch`: aceptar `allowed_providers`, validarlo como en las solicitudes, rechazar `firmar` con `422` y copiarlo a cada solicitud; incluir `signing_url` de lote en la respuesta
- [x] 1.5 Tests: contexto con los campos nuevos y sin binarios, lote con métodos permitidos, `firmar` rechazado, migración sobre base existente

## 2. Credencial, página y endpoints del widget para lotes (FIRDOC-34)

- [x] 2.1 Agregar la ruta `GET /sign/batch/{batch_id}` con cabeceras de widget y `404` sin detalle si no existe
- [x] 2.2 Crear `widget_batch_routes.py` con la dependencia `batch_auth` (token del lote) y el contexto del lote (ítems con nombre, páginas, tamaño, estado, versión y error)
- [x] 2.3 `POST /provider` del lote: actualiza el lote y sus solicitudes pendientes validando los métodos permitidos
- [x] 2.4 `POST /prepare` y `POST /complete` del lote reutilizando `signature_batch`, con `X-Session-Ref` como en el flujo individual
- [x] 2.5 `GET /download`: ZIP en archivo temporal con los PDF vigentes de los firmados, nombres saneados y únicos, `no-store`, `409` si no hay firmados
- [x] 2.6 `POST /retry`: nuevo lote con los fallidos del lote terminado, devuelve id y `signing_url`; `409` sin fallidos o sin terminar
- [x] 2.7 Tests de seguridad: token cruzado (lote↔solicitud↔otro lote), sin token, vencido, alterado, API key rechazada, página `404` y `frame-ancestors`
- [x] 2.8 Tests de flujo con `local`: completo, éxito parcial con un documento fallido, ZIP con solo los firmados, reintento que no vuelve a firmar los firmados

## 3. Carga de varios PDF desde el panel (backend)

- [x] 3.1 `upload_batch` en `services/panel_upload.py`: validar todos los PDF antes de insertar, crear el lote en el sistema interno con `token`/`local` habilitados y devolver los metadatos
- [x] 3.2 `POST /api/v1/admin/signing-batch-uploads` con esquemas (2 a `max_batch_size`, `filename`, `document_base64`, `signer` opcional) y evento `panel_batch_upload`
- [x] 3.3 Tests: lote válido, un archivo inválido sin dejar filas, cantidad fuera de rango, sin token, auditoría sin contenido

## 4. Cliente del widget: modo y datos de lote (FIRDOC-34)

- [x] 4.1 `bootstrap/token.ts`: devolver el tipo (solicitud o lote) y el id desde `/sign/{id}` y `/sign/batch/{id}`; adaptar `main.tsx`
- [x] 4.2 Tipos y cliente del servidor para los endpoints de lote (contexto, método, preparar, completar, descarga, reintento); extender `guards.ts`
- [x] 4.3 Mensajes en `messages/es.ts` para las pantallas de lote y los errores por documento
- [x] 4.4 Tests de arranque y de cliente: ambos tipos de enlace, token fuera de la URL, errores de red y de formato

## 5. Máquina y flujo del lote en el widget (FIRDOC-34)

- [x] 5.1 Adaptar la máquina existente al lote (el lote como `WidgetContext` con bloque `batch`; la revisión es la pantalla de elección aun con un solo método) sin romper la firma individual
- [x] 5.2 Extender `useSigningFlow`: estado del agente para la elección, notificación de lote y acción de reintento; el cliente de lote reutiliza prepare/complete de una sola vez
- [x] 5.3 Tests de la máquina y del hook: un solo `prepare`, una sola llamada de firma al agente con N desafíos, un solo `complete`, PIN incorrecto y vencido, rechazo antes del PIN, cancelar
- [x] 5.4 Notificación al anfitrión `firmadoc:batch-completed` sin PDF ni token en `embed/hostMessages.ts`, con test de datos sensibles

## 6. Pantallas del lote y tarjetas de método (FIRDOC-34, 35)

- [x] 6.1 Componente de tarjetas de método con etiquetas de validez, `radiogroup` accesible, indicador del agente y tarjeta de `firmar` deshabilitada en lotes; usarlo en `ChooseProvider`
- [x] 6.2 Verificar con el agente real sobre SoftHSM (WSL) que firma N desafíos con un PIN y que su diálogo muestra la cantidad; ajustar solo si no (ya cubierto: `agent/tests/test_agent_pkcs11.py` firma 2 y 3 hashes con un PIN sobre SoftHSM y `ui_tk.py` muestra la cantidad; sin cambios en el agente)
- [x] 6.3 Tarjeta del documento (nombre, páginas, tamaño, «Pendiente de firma» y vencimiento) en la firma individual
- [x] 6.4 Pantalla `BatchReview` (lista con nombre, páginas y tamaño, elección de método, «Firmar N documentos») y reutilización de las pantallas de certificado y PIN con la cantidad de documentos
- [x] 6.5 Pantalla `BatchResult` («N de M documentos firmados», estado por documento, «Descargar firmados (N)», «Reintentar» y «Cerrar») conectada a `useBatchFlow`
- [x] 6.6 Revisar certificados con vigencia (vencidos deshabilitados), rechazo antes del PIN, espera del PIN y éxito contra el mockup; ajustar textos y estilos
- [x] 6.7 Tests de pantallas (render, teclado, estados) y revisión de que no hay regresiones en `widget/tests`; recompilar `widget/dist`

## 7. Panel: varios PDF en «Firmar documento»

- [x] 7.1 `admin_ui`: aceptar varios archivos, listar con nombre, páginas y tamaño y «Quitar» por archivo, rechazar no-PDF sin enviar, aplicar el máximo de documentos
- [x] 7.2 Con más de un archivo llamar a `signing-batch-uploads`, embeber el widget de lote y mostrar el resultado de `firmadoc:batch-completed` validando origen y ventana
- [x] 7.3 Pruebas en Chrome real: lote de 3 con firma de demostración y resultado «3 de 3»; archivo inválido; mensaje de otra ventana ignorado

## 8. Punta a punta, documentación y cierre

- [x] 8.1 Prueba en Chrome real con el agente simulado y SoftHSM: lote con token, un solo PIN, éxito parcial forzado, descarga del ZIP y reintento
- [x] 8.2 Prueba en Chrome real de la nueva elección de método y de la tarjeta del documento en la firma individual
- [x] 8.3 Documentar: `docs/signature-batches.md` (método elegible, `signing_url`, widget de lote), `docs/admin.md` y la guía del widget (mensaje `firmadoc:batch-completed`)
- [x] 8.4 Ejecutar suite completa de backend, widget (tests, lint y typecheck) y e2e; corregir regresiones
- [x] 8.5 Pasar FIRDOC-34 y FIRDOC-35 a Listo en Jira al cerrar el change
