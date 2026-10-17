import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import ratelimit
from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import Request
from app.seeds import run

CONTRACT_KEYS = {"input", "normalized", "syllables", "zh", "ja", "request_id"}


@pytest.fixture()
def db() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        run(s)
        yield s


@pytest.fixture()
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    ratelimit.reset()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _post(client: TestClient, name: object) -> tuple[int, dict]:  # type: ignore[type-arg]
    r = client.post("/api/names/convert", json={"name": name})
    return r.status_code, r.json()


def _count_requests(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Request)) or 0


def test_response_matches_contract_for_dictionary_name(client: TestClient) -> None:
    status, body = _post(client, "Carlos")
    assert status == 200
    assert set(body) == CONTRACT_KEYS
    uuid.UUID(body["request_id"])
    assert body["input"] == "Carlos"
    assert body["normalized"] == "carlos"
    assert body["syllables"] == ["car", "los"]
    assert body["zh"][0] == {
        "rank": 1,
        "text": "卡洛斯",
        "pinyin": "kǎ luò sī",
        "chars": [
            {"char": "卡", "pinyin": "kǎ", "meaning": "tarjeta"},
            {"char": "洛", "pinyin": "luò", "meaning": "río Luo"},
            {"char": "斯", "pinyin": "sī", "meaning": "este"},
        ],
        "source": "dictionary",
        "verified": False,
    }
    assert body["ja"] == [
        {
            "rank": 1,
            "text": "カルロス",
            "romaji": "karurosu",
            "source": "dictionary",
            "verified": False,
        }
    ]


def test_unlisted_name_uses_algorithm_with_three_zh_alternatives(client: TestClient) -> None:
    _, body = _post(client, "Marta")
    assert [o["rank"] for o in body["zh"]] == [1, 2, 3]
    assert {o["source"] for o in body["zh"]} == {"algorithm"}
    assert body["ja"][0]["text"] == "マルタ"
    assert body["ja"][0]["source"] == "algorithm"


def test_multiple_words(client: TestClient) -> None:
    _, body = _post(client, "Ana María")
    assert body["normalized"] == "ana maria"
    assert body["syllables"] == ["a", "na", "ma", "rí", "a"]
    assert body["zh"][0]["text"] == "安娜·玛丽亚"
    assert body["ja"][0]["text"] == "アナ・マリア"
    assert body["ja"][0]["romaji"] == "ana maria"


def test_mixed_dictionary_and_algorithm_words_are_marked_algorithm(client: TestClient) -> None:
    _, body = _post(client, "Ana Marta")
    assert body["zh"][0]["source"] == "algorithm"
    assert body["ja"][0]["source"] == "algorithm"


def test_request_is_saved(client: TestClient, db: Session) -> None:
    _, body = _post(client, "Pablo")
    saved = db.get(Request, uuid.UUID(body["request_id"]))
    assert saved is not None
    assert saved.input_name == "Pablo"
    assert saved.locale == "es"
    assert saved.result_json == {k: v for k, v in body.items() if k != "request_id"}


@pytest.mark.parametrize(
    ("name", "fragment"),
    [
        ("", "Escribe"),
        ("   ", "Escribe"),
        ("Ana123", "Solo se permiten"),
        ("<script>", "Solo se permiten"),
        ("李明", "Solo se permiten"),
        ("x" * 61, "60"),
        ("a b c d e", "4 palabras"),
    ],
)
def test_invalid_names_rejected_without_saving(
    client: TestClient, db: Session, name: str, fragment: str
) -> None:
    status, body = _post(client, name)
    assert status == 422
    assert body["error"]["code"] == "invalid_name"
    assert fragment in body["error"]["message"]
    assert _count_requests(db) == 0


def test_malformed_body_uses_error_format(client: TestClient) -> None:
    status, body = _post(client, 123)
    assert status == 422
    assert body["error"]["code"] == "validation_error"
    r = client.post("/api/names/convert", json={})
    assert r.status_code == 422
    assert set(r.json()) == {"error"}
    assert set(r.json()["error"]) == {"code", "message"}


def test_unknown_route_and_method_use_error_format(client: TestClient) -> None:
    r = client.get("/api/nope")
    assert (r.status_code, r.json()["error"]["code"]) == (404, "not_found")
    r = client.get("/api/names/convert")
    assert (r.status_code, r.json()["error"]["code"]) == (405, "method_not_allowed")


def test_rate_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)
    assert [_post(client, "Ana")[0] for _ in range(3)] == [200, 200, 200]
    status, body = _post(client, "Ana")
    assert status == 429
    assert body["error"]["code"] == "rate_limited"


def test_health_unaffected(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
