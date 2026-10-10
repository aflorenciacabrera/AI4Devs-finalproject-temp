## 1. Opción `--database-url`

- [x] 1.1 `demo.prepare(..., database_url=None)`: usa la URL dada o la SQLite de `data/demo/`; `DemoEnv.external_database`; con base externa no se copia nada de `data/demo/storage/`: `storage_migrate.versions_without_blob` y, si falta alguno, mensaje sin `--reset` (`storage_migrate` o recrear la base).
- [x] 1.2 `demo.main`: argumento `--database-url`, validación con `make_url` antes de `--reset` (`DemoError` si no se interpreta).
- [x] 1.3 `demo.guide`: línea «Base:» con la URL sin contraseña (o `firmadoc-demo.db`), y con base externa cómo empezar de cero (`docker compose down -v`, que `--reset` no la toca).

## 2. Pruebas

- [x] 2.1 `tests/test_demo.py`: `--database-url` con una SQLite alternativa (esquema, seed y `stored_blob` en esa base; `firmadoc-demo.db` no se crea; variable de entorno; guía con la base y sin contraseña; `--reset` conserva la base externa); URL inválida → error sin crear `data/demo/`; versiones sin PDF en base externa → mensaje sin `--reset`.
- [x] 2.2 Prueba contra PostgreSQL real (`FIRMADOC_TEST_PG_URL`, se omite sin ella): preparar la demo, firmar desde el panel, versiones en `stored_blob`, arranque repetido sin duplicar el seed.
- [x] 2.3 `pytest tests -q --ignore=tests/e2e` (con `FIRMADOC_TEST_PG_URL` apuntando a `firmadoc_test`) y `ruff check` en verde.

## 3. Documentación

- [x] 3.1 `docs/demo.md` (sección «Con PostgreSQL»), `docs/database.md` (la demo sobre la base del proyecto), `README.md` (opciones de la demo y «Cómo correr todo en limpio»).

## 4. Verificación

- [x] 4.1 `python -m firmadoc.demo --prepare-only --database-url postgresql+psycopg://firmadoc:firmadoc@localhost:5432/firmadoc` sobre la base del proyecto: la guía muestra la base sin contraseña, el seed no se duplica y una firma desde el panel deja v1 y v2 en `stored_blob` de PostgreSQL.
