import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Antes de importar la app: su módulo principal lee la configuración al cargarse.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://gastos:gastos_local@localhost:5432/gastos_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.pop("DSQL_ENDPOINT", None)
os.environ.setdefault("S3_BUCKET", "bucket-de-prueba")
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ["COGNITO_USER_POOL_ID"] = "us-east-2_prueba"
os.environ["COGNITO_CLIENT_ID"] = "cliente-de-prueba"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, Engine, create_engine, make_url, text

from alembic import command
from app import auth
from app.db import get_engine
from app.main import app
from app.migrate import alembic_config
from tests.tokens import ISSUER, StubJwksClient, access_token

API_ROOT = Path(__file__).resolve().parents[1]


def _create_test_database(url: URL) -> None:
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        exists = connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        )
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """Base de prueba recién migrada. Requiere Postgres: `docker compose up -d postgres`."""
    url = make_url(TEST_DATABASE_URL)
    _create_test_database(url)
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    command.upgrade(alembic_config(), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db(migrated_engine: Engine) -> Iterator[Engine]:
    yield migrated_engine
    with migrated_engine.begin() as connection:
        connection.execute(text("TRUNCATE users CASCADE"))


@pytest.fixture
def verifier(monkeypatch: pytest.MonkeyPatch) -> auth.TokenVerifier:
    client: Any = StubJwksClient()
    instance = auth.TokenVerifier(ISSUER, "cliente-de-prueba", client)
    monkeypatch.setattr(auth, "get_token_verifier", lambda: instance)
    return instance


@dataclass
class Api:
    """Cliente que entra como un usuario, con un token firmado de verdad."""

    client: TestClient

    def as_user(self, sub: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token(sub=sub)}"}


@pytest.fixture
def api(db: Engine, verifier: auth.TokenVerifier) -> Api:
    return Api(TestClient(app))
