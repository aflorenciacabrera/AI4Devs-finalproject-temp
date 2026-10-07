# backend/

API de Firmadoc (FastAPI + SQLAlchemy + Alembic). Código en `src/firmadoc/`, migraciones en `migrations/`.

## Desarrollo

```bash
python -m venv .venv && .venv/Scripts/activate   # Windows (Git Bash: source .venv/Scripts/activate)
pip install -e ".[dev]"
alembic upgrade head                              # SQLite local por defecto
python -m firmadoc.seed                           # datos de demo
uvicorn firmadoc.main:app --reload
```

Base de datos: variable `FIRMADOC_DATABASE_URL` (ver `.env.example`).

## Tests

```bash
pytest                                            # SQLite
docker compose up -d postgres
FIRMADOC_TEST_PG_URL=postgresql+psycopg://firmadoc:firmadoc@localhost:5432/firmadoc pytest   # + PostgreSQL
```

Los tests de PostgreSQL recrean el esquema `public`: usar una base descartable.
