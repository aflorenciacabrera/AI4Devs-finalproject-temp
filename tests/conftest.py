import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from firmadoc.api.deps import settings_dep
from firmadoc.config import Settings
from firmadoc.db import make_engine
from firmadoc.main import app
from firmadoc.seed import DEMO_API_KEY, seed_demo

from .pki import Pki

ROOT = Path(__file__).resolve().parent.parent
PG_URL = os.environ.get("FIRMADOC_TEST_PG_URL")


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture(params=["sqlite", "postgres"])
def db_url(request, tmp_path):
    if request.param == "sqlite":
        yield f"sqlite:///{tmp_path / 'test.db'}"
        return
    if not PG_URL:
        pytest.skip("FIRMADOC_TEST_PG_URL no definida")
    engine = make_engine(PG_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    yield PG_URL


@pytest.fixture
def engine(db_url):
    command.upgrade(alembic_config(db_url), "head")
    eng = make_engine(db_url)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def settings(db_url, tmp_path, engine):
    return Settings(
        database_url=db_url,
        storage_dir=str(tmp_path / "storage"),
        local_cert_dir=str(tmp_path / "cert"),
        public_base_url="http://test",
        challenge_ttl_seconds=300,
    )


@pytest.fixture
def client(settings, session):
    seed_demo(session)  # sistema integrador demo con la API key DEMO_API_KEY
    app.dependency_overrides[settings_dep] = lambda: settings
    yield TestClient(app, headers={"X-API-Key": DEMO_API_KEY})
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def pki():
    return Pki()


@pytest.fixture(scope="session")
def anchors(pki, tmp_path_factory):
    directory = tmp_path_factory.mktemp("trust")
    pki.write_anchors(directory)
    return directory


@pytest.fixture
def token_env(settings, pki, anchors, tmp_path):
    """Servidor configurado para el proveedor token: anclas de la PKI de prueba y CRL local."""
    settings.trust_dir = str(anchors)
    settings.revocation_mode = "hard-fail"
    settings.revocation_fetch = False
    settings.crl_dir = str(tmp_path / "crl")
    pki.write_crls(Path(settings.crl_dir))
    return settings
