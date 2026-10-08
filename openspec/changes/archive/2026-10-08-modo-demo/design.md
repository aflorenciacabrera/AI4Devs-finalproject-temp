## Context

- La configuración se lee de variables `FIRMADOC_*` (`Settings`, `pydantic-settings`); las migraciones (`backend/migrations/env.py`) toman la URL de `sqlalchemy.url` o de `get_settings()`; el seed está en `firmadoc.seed` (`seed_demo(session, storage)`); `main:app` es la aplicación FastAPI.
- El proveedor `local` ya firma sin token; lo que falta es un arranque sin configuración manual. El panel exige que el origen coincida con `public_base_url` para embeber el widget.

## Goals / Non-Goals

**Goals:** un comando que prepare y arranque todo, idempotente, aislado de los datos habituales y con secretos estables.

**Non-Goals:** token USB simulado, despliegue público, tocar el modo real.

## Decisions

1. **Módulo `firmadoc.demo` con una función pura `prepare(dir, port)` y `main()`.** `prepare` crea la carpeta, lee o genera `demo.json`, fija las variables de entorno, migra y siembra, y devuelve los datos para mostrar; `main` solo parsea argumentos, imprime la guía y llama a `uvicorn.run`. Permite probar `prepare` sin levantar un servidor.
2. **Configuración por variables de entorno del propio proceso**, no por un `.env`: el servidor lee `Settings()` en cada pedido, así que alcanza con `os.environ`. Evita pisar el `.env` de la persona. Las variables de la demo se fijan siempre (la demo es determinística), salvo `FIRMADOC_REAL_MODE`, que se valida primero.
3. **Aislamiento en `data/demo/`**: `firmadoc-demo.db`, `storage/`, `local-cert/` y `demo.json`. `--reset` borra la carpeta entera (solo esa ruta, comprobando que su nombre sea `demo`).
4. **Secretos con `secrets.token_urlsafe(32)`**, guardados en `demo.json` (en una carpeta ignorada por git). Es material de demostración, no de producción; el archivo no se usa en modo real.
5. **Migraciones con la API de Alembic** (`command.upgrade(cfg, "head")`) con `sqlalchemy.url` fijado, igual que las pruebas; el seed con `LocalFileStorage` para que los PDF existan.
6. **El widget no se compila desde el comando**: depende de Node y red; se avisa con la instrucción exacta y el panel sigue funcionando.

## Risks / Trade-offs

- [Secretos de demo en un archivo] → solo para pruebas locales, `data/` ignorado por git, el comando se niega en modo real.
- [`--reset` borra datos] → solo dentro de `data/demo` y con la carpeta nombrada exactamente así.
- [`localhost` vs `127.0.0.1`] → la guía imprime siempre la URL con `localhost`, que es la configurada como origen del widget.
