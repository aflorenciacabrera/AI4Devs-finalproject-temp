## 1. Configuración y errores

- [x] 1.1 `tsa_url`, `tsa_timeout_seconds` y `tsa_required` en `Settings` (validar el esquema) y `.env.example`
- [x] 1.2 `ServiceUnavailable` (503) en `errors.py`
- [x] 1.3 `timestamping.py`: creación del sellador a partir de la configuración (sustituible en las pruebas)

## 2. Motor y flujo

- [x] 2.1 `finish_pdf` acepta un sellador y distingue el fallo de la TSA (`TimestampUnavailable`)
- [x] 2.2 Reordenar `complete`: armar y verificar el PDF antes de consumir el desafío, manteniendo el consumo atómico
- [x] 2.3 Política: B-T con sello, B-B sin TSA, `timestamp_unavailable` opcional, `503` obligatorio; nivel de la versión y datos del evento `signed`
- [x] 2.4 `verify_pdf` informa el sello (presente, fecha, íntegro, válido, de confianza) y `ok` lo exige; esquemas de `verify`

## 3. Pruebas

- [x] 3.1 Con TSA de prueba (`DummyTimeStamper`): nivel `B-T`, evento `signed`, descarga y verificación con pyHanko y con `openssl`
- [x] 3.2 Sin TSA: `B-B` y evento `timestamp: absent`
- [x] 3.3 TSA caída con sello opcional y obligatorio (503, desafío sin consumir, reintento exitoso después)
- [x] 3.4 Camino HTTP real contra un servidor local (éxito, error 500, tiempo agotado, respuesta inválida)
- [x] 3.5 `verify`: sello de confianza, TSA desconocida, firma sin sello, firma alterada
- [x] 3.6 Concurrencia y desafíos: las pruebas existentes de `complete` siguen pasando tras el reordenamiento; dos `complete` simultáneos con TSA producen una sola versión
- [x] 3.7 Con el proveedor `token`: B-T de punta a punta

## 4. Documentación y cierre

- [x] 4.1 Escribir `docs/timestamping.md` y enlazarlo desde `backend/README.md`
- [x] 4.2 Ejecutar `pytest` y `ruff check` sin errores
