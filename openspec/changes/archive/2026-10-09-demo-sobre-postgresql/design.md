## Context

Ver `proposal.md`. `demo.prepare()` arma la URL SQLite a partir de la carpeta, la fija en `FIRMADOC_DATABASE_URL`, corre Alembic con esa URL, migra los PDF de disco y carga el seed con `DatabaseStorage`. Nada en ese camino depende del dialecto: la migración 0006 y `DatabaseStorage` ya se prueban contra PostgreSQL (`FIRMADOC_TEST_PG_URL`). La base PostgreSQL del proyecto (`docker-compose.yml`) ya está en la migración 0006 con sus PDF en `stored_blob`.

## Goals / Non-Goals

**Goals:** una sola opción nueva; el resto de la demo idéntico con cualquier base; nunca tocar una base externa de forma destructiva.

**Non-Goals:** gestionar el contenedor; validar que la URL sea PostgreSQL (cualquier dialecto que SQLAlchemy y las migraciones soporten vale, y así se prueba también con una SQLite alternativa).

## Decisions

1. **`prepare(directory, port, signer, database_url=None)`.** Con `None` se arma la SQLite de siempre. `DemoEnv.database_url` ya existe y pasa a reflejar la base en uso; se agrega `external_database: bool` para la guía y los mensajes.
2. **Validar con `sqlalchemy.engine.make_url` en `main`, antes de `--reset` y de tocar el disco.** Un `ArgumentError` se convierte en `DemoError`. La contraseña nunca se imprime: la guía usa `render_as_string(hide_password=True)`.
3. **`--reset` no toca la base externa.** Borrar un esquema por una opción de línea de comandos es demasiado peligroso para una base que puede no ser la del proyecto. El seed es idempotente y los secretos de `data/demo/` no dependen de la base, así que `--reset` + base externa sigue funcionando. La guía dice `docker compose down -v` (base del proyecto) para empezar de cero.
4. **Con base externa no se copia nada del disco; solo se comprueba.** `data/demo/storage/` pertenece a la base SQLite de la demo: sus archivos son versiones de *esa* base, y el seed usa referencias fijas (`demo/EXP-DEMO-001/v1.pdf`) que chocarían con el seed de la base externa (se detectó al probar contra la base del proyecto: «conflicto» en los dos PDF del seed). Por eso con `--database-url` se usa `storage_migrate.versions_without_blob(session)`: si alguna versión registrada no tiene binario en `stored_blob`, el mensaje la lista y sugiere `FIRMADOC_STORAGE_DIR=<carpeta> python -m firmadoc.storage_migrate files-to-database` o recrear la base, no `--reset`.
5. **Pruebas.** Unitarias con una SQLite alternativa (`sqlite:///<tmp>/otra.db`) para la opción, la guía y la URL inválida, sin depender de Docker; una prueba contra PostgreSQL real con `FIRMADOC_TEST_PG_URL` (recrea el esquema `public` como el resto de la suite) que prepara la demo, firma desde el panel y cuenta `stored_blob`.

## Risks / Trade-offs

- [Correr la demo contra una base que no es de demostración] → el seed crea un integrador de demostración con API key conocida; la documentación lo advierte y la demo ya se niega en modo real.
- [Alembic sobre una base con otra versión del esquema] → `upgrade head` es el mismo que usa la instalación normal; si falla, el error de Alembic se muestra tal cual.
- [Otra sesión edita el widget sin commitear] → no se toca el widget; `git add` por rutas.

## Migration Plan

Sin migraciones. Rollback: revertir el commit; la base externa queda como esté (los datos de demo no estorban).
