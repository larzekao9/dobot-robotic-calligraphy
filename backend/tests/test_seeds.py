from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base
from app.seeds import DATA_DIR, _rows, run


@pytest.fixture()
def db() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_seed_counts(db: Session) -> None:
    n_names = len(_rows("names_seed.csv", DATA_DIR))
    n_syl = len(_rows("syllables_zh.csv", DATA_DIR)) + len(_rows("syllables_ja.csv", DATA_DIR))
    run(db)
    assert _count(db, models.NameDictionary) == n_names
    assert _count(db, models.NameTransliteration) == n_names * 2
    assert _count(db, models.SyllableMap) == n_syl


def test_seed_idempotent_and_unverified(db: Session) -> None:
    run(db)
    assert run(db) == {"names": 0, "syllables": 0, "glyphs": 0}
    assert db.scalar(select(func.count()).where(models.NameDictionary.verified.is_(True))) == 0


def test_avoid_only_in_zh_seed(db: Session) -> None:
    run(db)
    avoid = models.SyllableMap.connotation == models.Connotation.avoid
    assert db.scalar(
        select(func.count()).where(avoid, models.SyllableMap.script == models.Script.zh)
    )
    assert not db.scalar(
        select(func.count()).where(avoid, models.SyllableMap.script == models.Script.ja)
    )
