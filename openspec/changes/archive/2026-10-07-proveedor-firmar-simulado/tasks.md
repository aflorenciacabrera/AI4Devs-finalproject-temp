## 1. Base y configuración

- [x] 1.1 `remote_operation_id` en el modelo y migración `0004` reversible (índice único) con su prueba
- [x] 1.2 Variables `firmar_*` en `Settings` (validar secretos) y `.env.example`

## 2. Adaptador

- [x] 2.1 Cliente del servicio (`providers/firmar.py`): OAuth2 client credentials, envío del documento, transporte inyectable, errores `503` genéricos
- [x] 2.2 Habilitar `firmar` en `get_provider` solo con URL base
- [x] 2.3 Extraer `_register_signed` de `complete` sin cambiar su comportamiento
- [x] 2.4 `prepare` remoto (operación, `signing`, bloque `remote`, sin desafío) y `complete` → `409 remote_signature_pending`
- [x] 2.5 Callback: HMAC, búsqueda por operación, idempotencia, rechazo/vencimiento y validación del PDF (prefijo, una firma más, cadena, CUIL), registro del certificado y de la versión

## 3. Simulado

- [x] 3.1 `mock_firmar.py`: AC propia, token OAuth, operaciones, aprobar (OTP/PIN, bloqueo) y rechazar, firma con pyHanko y llamada al callback
- [x] 3.2 Rutas solo con la bandera y su AC como ancla de verificación

## 4. Pruebas

- [x] 4.1 Habilitación y configuración
- [x] 4.2 Simulado: token, credenciales inválidas, operaciones, OTP/PIN y bloqueo, un documento por operación
- [x] 4.3 Flujo completo (crear, preparar, aprobar, callback) con verificación del PDF y del certificado, y con webhook
- [x] 4.4 Callback: firma HMAC inválida, operación desconocida, repetición, rechazo y vencimiento
- [x] 4.5 Validación del PDF devuelto: contenido alterado, sin firma nueva, dos firmas, cadena desconocida, CUIL distinto, cuerpo inválido
- [x] 4.6 Servicio caído o con credenciales malas en `prepare`
- [x] 4.7 Camino HTTP real contra un servidor local (no solo transporte en memoria)

## 5. Documentación y cierre

- [x] 5.1 `docs/firmar.md` (contrato simulado, qué cambiar para el servicio real, supuestos) y enlace desde `backend/README.md`
- [x] 5.2 Ejecutar `pytest` y `ruff check` sin errores
