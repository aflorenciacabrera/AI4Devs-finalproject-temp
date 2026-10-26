## 1. Comando de demostración (FIRDOC-46)

- [x] 1.1 Crear `firmadoc/demo.py` con `prepare(dir, port)`: carpeta, secretos persistentes en `demo.json`, variables de entorno, migraciones y seed con almacenamiento de archivos
- [x] 1.2 Rechazar `FIRMADOC_REAL_MODE` activo antes de crear o modificar nada, e implementar `--reset` acotado a la carpeta `demo`
- [x] 1.3 Implementar `main()`: argumentos `--port`, `--host`, `--reset`, aviso de widget sin compilar, guía de uso y arranque con `uvicorn`
- [x] 1.4 Verificar que `data/demo/` queda ignorado por git

## 2. Pruebas y documentación

- [x] 2.1 Tests: primer arranque (esquema, seed, archivos), arranque repetido sin duplicar, secretos estables, `--reset`, rechazo en modo real sin tocar nada, aviso de widget ausente
- [x] 2.2 Test de humo: con el entorno preparado, el panel inicia sesión con el token generado y se firma un PDF con «Firma propia»
- [x] 2.3 Documentar en `docs/demo.md` y verificar el comando de verdad (arrancar, `/health`, `/admin`)
- [x] 2.4 Suite completa y linter; pasar FIRDOC-46 a Listo en Jira al cerrar
