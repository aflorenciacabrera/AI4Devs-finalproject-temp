## 1. Spike y dependencias

- [x] 1.1 Agregar `pyhanko`, `pyhanko-certvalidator` y `cryptography` a `pyproject.toml` e instalar
- [x] 1.2 Spike (script descartable en `tests/`): firmar un PDF con la API de firma interrumpida en dos pasos, calculando el hash de los atributos firmados y firmándolo con una clave RSA externa; confirmar que el resultado valida y documentar la secuencia exacta de llamadas en `design.md`
- [x] 1.3 Helper de tests que genera un PDF mínimo válido

## 2. Configuración, almacenamiento y autenticación

- [x] 2.1 Ampliar `Settings` con `storage_dir`, `local_cert_dir`, `public_base_url`, `challenge_ttl_seconds` y `max_document_bytes`, y actualizar `.env.example`
- [x] 2.2 Implementar `DocumentStorage` (Protocol) y `LocalFileStorage` con `save` inmutable, `read` y rechazo de rutas fuera del directorio
- [x] 2.3 Tests de almacenamiento: guardar, no sobrescribir, hash coherente y ruta maliciosa
- [x] 2.4 Dependencia de sesión de base de datos y dependencia de autenticación `X-API-Key` (hash SHA-256, `401` si falta o no coincide)
- [x] 2.5 Tests de autenticación: clave ausente, inválida y válida

## 3. Proveedor local

- [x] 3.1 Definir la interfaz `SignatureProvider` y los tipos de intercambio (`PreparedSignature`)
- [x] 3.2 Generar y cargar el certificado autofirmado de demostración en `FIRMADOC_LOCAL_CERT_DIR` (permisos restringidos) y registrar su `Certificate` una sola vez
- [x] 3.3 Implementar `LocalPAdESProvider` (firma el hash con la clave propia)
- [x] 3.4 Tests: primer uso crea el certificado, el reinicio lo reutiliza, la clave no queda dentro del repositorio

## 4. Servicio de flujo de firma

- [x] 4.1 Servicio de documentos: resolver `document_id`/`document_base64`, validar PDF y tamaño, crear `Document` y versión 1 `uploaded` con su hash
- [x] 4.2 Alta/reutilización de `Signer` y creación de la `SignatureRequest` con `signing_url` y evento `created`
- [x] 4.3 `prepare`: reservar espacio de firma, calcular el hash, guardar el estado intermedio en `prepared/{challenge_id}/`, crear el `SigningChallenge` (TTL, `session_ref`), pasar a `signing` y registrar `prepared`
- [x] 4.4 `complete`: validar desafío (vigente, no consumido, misma sesión), consumirlo de forma atómica, verificar la firma contra el hash, incrustarla, guardar el binario y crear la versión `signed` vigente con `signing_status` y estado de la solicitud, todo en una transacción; registrar `signed` o `failed`
- [x] 4.5 Consulta de la solicitud con bloque `document` y eventos de auditoría
- [x] 4.6 Descarga de una versión por `document_id` y número, filtrada por sistema integrador

## 5. API

- [x] 5.1 Schemas Pydantic de request/response según la sección 4 del README
- [x] 5.2 Routers `POST /signature-requests`, `POST .../{id}/prepare`, `POST .../{id}/complete`, `GET .../{id}` y `GET /documents/{id}/versions/{n}/download`
- [x] 5.3 Mapeo de errores de dominio a `401`, `404`, `409` y `422` con el motivo en el cuerpo
- [x] 5.4 Rechazo de `provider` `token` y `firmar` con `422` mientras no estén habilitados

## 6. Tests de la API

- [x] 6.1 Flujo feliz `local` de punta a punta: la versión 2 es `signed`, vigente y descargable, y la versión 1 permanece intacta
- [x] 6.2 La firma validada con `pyhanko.sign.validation` (y con `openssl` si está disponible) y el hash de cada versión coincide con su binario
- [x] 6.3 Segunda firma sobre el mismo documento genera la versión 3 sin tocar las anteriores
- [x] 6.4 Errores de `create`: sin API key, PDF inválido, demasiado grande, documento de otro integrador, proveedor no habilitado
- [x] 6.5 Errores de `prepare`/`complete`: estado inválido, desafío vencido, reutilizado y de otra sesión, firma que no verifica (solicitud `failed`)
- [x] 6.6 Dos `complete` simultáneos sobre el mismo desafío: solo uno tiene éxito
- [x] 6.7 Los eventos de auditoría `created`, `prepared`, `signed` y `failed` se registran en orden

## 7. Documentación y cierre

- [x] 7.1 Documentar en `backend/README.md` cómo recorrer el flujo con `curl` usando el seed y la API key demo
- [x] 7.2 Ejecutar `pytest` y `ruff check` sin errores
