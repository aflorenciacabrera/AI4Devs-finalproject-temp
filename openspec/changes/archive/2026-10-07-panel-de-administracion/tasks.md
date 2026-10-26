## 1. Base y acceso

- [x] 1.1 Modelo `AdminEvent` y migración `0003` reversible con sus triggers (SQLite y PostgreSQL); prueba de migración
- [x] 1.2 `admin_token` en `Settings` (≥ 32 caracteres) y `.env.example`
- [x] 1.3 Dependencia de autenticación de administración (404 sin token configurado, 401 si es inválido, comparación en tiempo constante) y función para registrar `admin_event`
- [x] 1.4 `GET /admin/events` con paginación

## 2. Auditoría

- [x] 2.1 Listado de solicitudes con filtros, paginación y total (escapando comodines)
- [x] 2.2 Cadena de custodia de un documento sin secretos
- [x] 2.3 Listado de entregas de webhook y reenvío de las fallidas

## 3. Confianza

- [x] 3.1 Listar, agregar y quitar anclas (validación del certificado, sin sobrescribir, invalidando la caché de `load_trust_store`)
- [x] 3.2 Rotación del certificado propio (archivo del público, destrucción de la clave, nuevo par, caché del proveedor) y consulta
- [x] 3.3 La verificación de documentos usa los certificados propios archivados

## 4. Panel web

- [x] 4.1 Estáticos `admin_ui/` (HTML, CSS, JS sin `innerHTML`) y ruta `/admin` con CSP estricta
- [x] 4.2 Secciones: solicitudes con filtros, custodia, webhooks (reenviar), anclas (agregar y quitar), certificado (rotar), eventos; confirmaciones

## 5. Pruebas

- [x] 5.1 Acceso: sin token configurado, token inválido, API key de integrador, token corto
- [x] 5.2 Listado: filtros combinados, firmante por CUIL y por texto con comodines, paginación y parámetros inválidos
- [x] 5.3 Custodia y webhooks (reenvío válido e inválido) y registro de `admin_event`
- [x] 5.4 Anclas: agregar (una cadena pasa a ser de confianza), duplicado, inválidos, quitar y archivo con varios certificados
- [x] 5.5 Rotación: nuevas firmas con el certificado nuevo, clave vieja destruida y verificación de documentos anteriores
- [x] 5.6 Página: cabeceras, 404 deshabilitada y una prueba en Chrome real (ingreso, listado, token inválido, texto hostil sin ejecutarse, confirmación)

## 6. Documentación y cierre

- [x] 6.1 Escribir `docs/admin.md` y enlazarlo desde `backend/README.md`
- [x] 6.2 Ejecutar `pytest` y `ruff check` sin errores
