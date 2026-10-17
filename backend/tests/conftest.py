"""Fixtures compartidas por los tests de API: una base en memoria con seeds, sesión por petición
(como en producción) y un ejecutor de trabajos con simulador instantáneo."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import ratelimit
from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.seeds import run
from app.services.jobs import JobRunner, get_runner
from app.services.robot.mock_driver import MockDriver

ADMIN = {"X-Admin-Token": "test-token"}


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        run(s)
    yield eng


@pytest.fixture()
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


@pytest.fixture()
def runner(engine: Engine) -> JobRunner:
    return JobRunner(sessionmaker(bind=engine), lambda: MockDriver(time_scale=0))


@pytest.fixture()
def api(engine: Engine, runner: JobRunner, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    def override_db() -> Iterator[Session]:
        with Session(engine) as s:
            yield s

    monkeypatch.setattr(settings, "admin_token", "test-token")
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_runner] = lambda: runner
    ratelimit.reset()
    yield TestClient(app)
    app.dependency_overrides.clear()
