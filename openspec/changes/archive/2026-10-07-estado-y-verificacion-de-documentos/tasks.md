## 1. Verificación en el motor

- [x] 1.1 Agregar `verify_pdf(pdf, roots, other_certs)` a `pdf_engine.py` que devuelva el estado por firma (campo, sujeto, serie, fecha declarada, íntegra, válida, confiable, nivel de modificación)
- [x] 1.2 Función que arma las anclas de verificación (anclas configuradas + certificado del proveedor `local` si existe)

## 2. Servicio y API

- [x] 2.1 `services/documents.py`: consultar, cambiar estado y plazo, listar firmantes y verificar
- [x] 2.2 Esquemas y rutas `GET/PATCH /documents/{id}`, `GET /documents/{id}/signatures` y `POST /documents/{id}/verify`

## 3. Pruebas

- [x] 3.1 Estado y plazo: transiciones permitidas y prohibidas, plazo sin zona o pasado, cuerpo vacío, `deadline_passed`, aislamiento entre integradores y API key
- [x] 3.2 Firmantes: uno, dos sucesivos y ninguno
- [x] 3.3 Verificar con `local` y con `token`, con dos firmas, con binario alterado, con ancla desconocida, sin firmas y con binario ausente
- [x] 3.4 Contrastar el resultado con una herramienta independiente de pyHanko (`openssl` sobre la firma CMS)

## 4. Documentación y cierre

- [x] 4.1 Escribir `docs/documents-api.md` y enlazarlo desde `backend/README.md`
- [x] 4.2 Ejecutar `pytest` y `ruff check` sin errores
