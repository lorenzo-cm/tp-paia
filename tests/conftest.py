"""Shared test fixtures.

Hosts the disposable-Postgres DB fixtures (relocated from
``tests/db/conftest.py`` so suites outside ``tests/db/`` — e.g. the message
pipeline integration tests — can reuse the same db_hardening infra instead of
duplicating testcontainers wiring). DB tests are skipped when Docker is
unavailable so CI without Docker stays green.
"""

import os
import shutil
import subprocess
from collections.abc import Generator

import pytest
from docker.errors import DockerException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.main import app

_DB_FIXTURES = {"postgres_url", "db_engine", "db_session"}


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001
    items: list[pytest.Item],
) -> None:
    """Skip db tests when Docker is unavailable so CI without Docker stays green.

    Covers both the legacy ``tests/db/`` tree and any test elsewhere that
    requests a DB fixture (e.g. the message pipeline integration tests).
    """
    if shutil.which("docker") is not None:
        return
    skip_marker = pytest.mark.skip(reason="docker not available — db tests need it")
    for item in items:
        uses_db = bool(_DB_FIXTURES & set(getattr(item, "fixturenames", [])))
        if "tests/db/" in str(item.fspath) or uses_db:
            item.add_marker(skip_marker)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Boot Postgres 18.3 in Docker and run migrations against it.

    Returns the SQLAlchemy URL pointing at the migrated schema.
    """
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers[postgres] not installed")

    try:
        container = PostgresContainer("postgres:18.3")
        container.start()
    except DockerException as exc:
        pytest.skip(f"docker unavailable for db tests: {exc}")
    try:
        raw_url = container.get_connection_url()
        # testcontainers ships psycopg2 in the URL; we use psycopg3.
        url = raw_url.replace("postgresql+psycopg2://", "postgresql+psycopg://")

        env = {
            **os.environ,
            "DATABASE_URL": url,
            "ALEMBIC_NO_CONFIRM": "1",
        }
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"alembic upgrade failed:\nSTDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

        yield url
    finally:
        container.stop()


@pytest.fixture(scope="session")
def db_engine(postgres_url: str) -> Engine:
    engine = create_engine(postgres_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Session:
    """Per-test session bound to a SAVEPOINT that always rolls back.

    Pattern: open a connection, begin a transaction, give the session a
    nested SAVEPOINT for autoflush behavior. Tearing down rolls back the
    outer transaction so the database returns to its post-migration state.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
