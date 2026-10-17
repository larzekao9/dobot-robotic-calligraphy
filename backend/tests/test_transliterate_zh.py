from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Connotation, Gender, SyllableMap
from app.seeds import run
from app.services.transliterate_zh import transliterate_zh


def _session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return Session(engine)


@pytest.fixture()
def db() -> Iterator[Session]:
    with _session() as s:
        run(s)
        yield s


def _avoid_chars(db: Session) -> set[str]:
    rows = db.scalars(
        select(SyllableMap.output).where(SyllableMap.connotation == Connotation.avoid)
    )
    return set(rows)


def test_dictionary_name_returns_curated_version(db: Session) -> None:
    r = transliterate_zh(db, "Carlos")
    top = r.candidates[0]
    assert (top.text, top.pinyin, top.source) == ("卡洛斯", "kǎ luò sī", "dictionary")
    assert [c.char for c in top.chars] == ["卡", "洛", "斯"]
    assert top.chars[0].meaning == "tarjeta"


def test_dictionary_lookup_ignores_accents_and_case(db: Session) -> None:
    assert transliterate_zh(db, "MARÍA").candidates[0].text == "玛丽亚"


@pytest.mark.parametrize(
    ("name", "top"),
    [
        ("Marta", "马尔塔"),
        ("Bruno", "布鲁诺"),
        ("Tristán", "特里斯坦"),
        ("Manuel", "马努艾尔"),
        ("Cristian", "克里斯蒂安"),
        ("Rosa", "罗萨"),
    ],
)
def test_algorithm_first_choice(db: Session, name: str, top: str) -> None:
    r = transliterate_zh(db, name)
    assert r.missing == []
    assert r.candidates[0].text == top
    assert r.candidates[0].source == "algorithm"
    assert not r.candidates[0].verified


@pytest.mark.parametrize("name", ["Marta", "Bruno", "Lorena", "Valeria", "Ximena Pérez"])
def test_unlisted_names_give_three_alternatives(db: Session, name: str) -> None:
    r = transliterate_zh(db, name.split()[0])
    assert len(r.candidates) == 3
    assert len({c.text for c in r.candidates}) == 3
    assert [c.rank for c in r.candidates] == [1, 2, 3]


@pytest.mark.parametrize(
    "name", ["Nuria", "Silvia", "Kuno", "Sandra", "Gustavo", "Dario", "Moises", "Paula"]
)
def test_never_uses_avoid_characters(db: Session, name: str) -> None:
    avoid = _avoid_chars(db)
    assert avoid  # el seed incluye caracteres a evitar con puntaje alto
    for cand in transliterate_zh(db, name).candidates:
        assert not set(cand.text) & avoid, cand.text


def test_avoid_character_loses_even_with_top_score(db: Session) -> None:
    assert transliterate_zh(db, "Nuria").candidates[0].text.startswith("努")


def test_avoids_repeating_the_same_character(db: Session) -> None:
    top = transliterate_zh(db, "Nana").candidates[0].text
    assert top[0] != top[1]


def test_gender_prefers_matching_characters(db: Session) -> None:
    f = transliterate_zh(db, "Lina", Gender.f).candidates[0].text
    assert f in ("丽娜", "莉娜")  # 丽 y 莉 empatan; ambos femeninos


def test_multiple_words_use_middle_dot(db: Session) -> None:
    r = transliterate_zh(db, "Carlos Marta")
    assert r.candidates[0].text == "卡洛斯·马尔塔"
    assert len(r.candidates[0].chars) == 6


def test_chars_carry_pinyin_and_meaning(db: Session) -> None:
    c = transliterate_zh(db, "Bruno").candidates[0].chars[1]
    assert (c.char, c.pinyin, c.meaning) == ("鲁", "lǔ", "apellido / torpe")


def test_unmapped_units_reported_not_invented() -> None:
    with _session() as empty:
        r = transliterate_zh(empty, "Marta")
    assert r.candidates == []
    assert "ma" in r.missing


def test_empty_name(db: Session) -> None:
    assert transliterate_zh(db, "").candidates == []
