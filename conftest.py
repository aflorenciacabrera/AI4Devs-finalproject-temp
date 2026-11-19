"""Niveles de la suite: cada test se marca por lo que ARRANCA, no por la carpeta en la que está.

- `e2e`: un navegador real contra el servidor, el agente y una página anfitriona (tests/e2e).
- `functional`: arranca la aplicación, una base de datos, un servidor HTTP, un proceso o SoftHSM.
- `unit`: nada de lo anterior; una regla sola, con sus bordes.

`pytest -m unit` corre el nivel rápido (`make test-unit`). El recuento por nivel sale con
`pytest --collect-only -q -m <nivel>` y está en el README (2.6). Un test puede fijar su nivel a mano con
`@pytest.mark.<nivel>`; si no, se deduce acá. Ante la duda se marca hacia arriba: un test que quizá
arranca algo no cuenta como unitario.
"""

import re
from functools import cache
from pathlib import Path

import pytest

LEVELS = ("unit", "functional", "e2e")
# Fixtures de tests/conftest.py que levantan la base o la aplicación.
APP_FIXTURES = {"db_url", "engine", "session", "settings", "client", "token_env"}
# Señales, en el código del módulo de pruebas, de que algo se pone en marcha.
STARTS_SOMETHING = re.compile(
    r"TestClient\(|uvicorn|subprocess|HTTPServer|serve_forever|softhsm|make_server|tkinter|\bTk\(", re.IGNORECASE
)


@cache
def _module_starts_something(path: str) -> bool:
    try:
        return bool(STARTS_SOMETHING.search(Path(path).read_text(encoding="utf-8")))
    except OSError:
        return True


def level_of(item: pytest.Item) -> str:
    explicit = [name for name in LEVELS if item.get_closest_marker(name)]
    if explicit:
        return explicit[-1]
    path = Path(str(item.fspath))
    if "e2e" in path.parts:
        return "e2e"
    if APP_FIXTURES & set(getattr(item, "fixturenames", ())) or _module_starts_something(str(path)):
        return "functional"
    return "unit"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        level = level_of(item)
        if not item.get_closest_marker(level):
            item.add_marker(getattr(pytest.mark, level))
