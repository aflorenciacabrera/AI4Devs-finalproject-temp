## 1. Configuración y verificación

- [x] 1.1 `real_mode` en `Settings` y `.env.example`
- [x] 1.2 `preflight.py`: hallazgos (error, advertencia, información) como función pura y comando `python -m firmadoc.preflight`
- [x] 1.3 Verificación al arrancar en modo real (fallar con todos los errores)

## 2. Comportamiento

- [x] 2.1 Proveedor `local` no habilitado en modo real (también en `allowed_providers`)
- [x] 2.2 El seed se niega en modo real

## 3. Pruebas

- [x] 3.1 Tabla de casos de la verificación previa: cada error, cada advertencia, varios errores juntos, modo demostración, comando y códigos de salida
- [x] 3.2 Arranque: falla con configuración insegura (todos los errores) y arranca con la válida
- [x] 3.3 `local` rechazado en modo real y `token` permitido; modo demostración sin cambios
- [x] 3.4 Seed rechazado en modo real y funcional fuera de él

## 4. Documentación y cierre

- [x] 4.1 `docs/real-mode.md` con los pasos para el mToken CryptoID y los límites sin probar; enlace desde `backend/README.md`
- [x] 4.2 Ejecutar `pytest` y `ruff check` sin errores
