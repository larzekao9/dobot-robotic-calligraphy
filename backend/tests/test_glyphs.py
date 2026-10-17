import gzip
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Glyph, GlyphScript
from app.seeds import run
from app.services.glyph_chars import required_chars
from app.services.stroke_import import (
    catmull_rom,
    parse_kanjivg,
    parse_mmah,
    parse_svg_path,
    resample,
)


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
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- integridad de los datos importados ------------------------------------------------------


def test_every_emittable_char_has_a_glyph(db: Session) -> None:
    have = {(g.script, g.char) for g in db.scalars(select(Glyph))}
    missing = {
        (script.value, ch)
        for script, chars in required_chars(db).items()
        for ch in chars
        if (script, ch) not in have
    }
    assert not missing, f"sin trazos: {sorted(missing)}"


def test_required_chars_cover_seeds_and_algorithm(db: Session) -> None:
    req = required_chars(db)
    assert {"卡", "洛", "斯"} <= req[GlyphScript.zh]  # diccionario
    assert {"ン", "ィ", "ャ", "ル"} <= req[GlyphScript.ja_kana]  # tablas del algoritmo
    assert not ({"·", "・"} & (req[GlyphScript.zh] | req[GlyphScript.ja_kana]))


def test_glyph_geometry_is_normalized(db: Session) -> None:
    glyphs = db.scalars(select(Glyph)).all()
    assert len(glyphs) > 200
    for g in glyphs:
        assert g.stroke_count == len(g.strokes_json) >= 1, g.char
        assert g.source
        for stroke in g.strokes_json:
            assert 12 <= len(stroke) <= 30, (g.char, len(stroke))
            for x, y in stroke:
                assert -50 <= x <= 1074 and -50 <= y <= 1074, (g.char, x, y)


@pytest.mark.parametrize(("script", "char", "strokes"), [("zh", "卡", 5), ("ja_kana", "ア", 2)])
def test_known_stroke_counts(db: Session, script: str, char: str, strokes: int) -> None:
    g = db.scalar(select(Glyph).where(Glyph.script == GlyphScript(script), Glyph.char == char))
    assert g is not None and g.stroke_count == strokes


# --- API -------------------------------------------------------------------------------------


def test_get_glyph(client: TestClient) -> None:
    r = client.get("/api/glyphs/zh/卡")
    assert r.status_code == 200
    body = r.json()
    assert (body["char"], body["script"], body["stroke_count"]) == ("卡", "zh", 5)
    assert len(body["strokes"]) == 5
    assert "Arphic" in body["source"]
    kana = client.get("/api/glyphs/ja_kana/ア").json()
    assert "KanjiVG" in kana["source"] and kana["stroke_count"] == 2


def test_glyph_errors_use_error_format(client: TestClient) -> None:
    r = client.get("/api/glyphs/zh/龘")
    assert (r.status_code, r.json()["error"]["code"]) == (404, "glyph_not_found")
    assert client.get("/api/glyphs/klingon/卡").json()["error"]["code"] == "validation_error"
    assert client.get("/api/glyphs/zh/卡洛").json()["error"]["code"] == "validation_error"


# --- unidades del importador -----------------------------------------------------------------


def test_parse_svg_path_absolute_and_relative() -> None:
    assert parse_svg_path("M0,0 L10,0 V10 H0 Z") == [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    pts = parse_svg_path("M10,10 l5,0 l0,5")
    assert pts == [(10, 10), (15, 10), (15, 15)]


def test_parse_svg_path_cubic_ends_at_target() -> None:
    pts = parse_svg_path("M0,0c10,0,20,10,30,30s20,10,30,0")
    assert pts[0] == (0, 0)
    assert pts[-1] == pytest.approx((60, 30))
    assert len(pts) > 20


def test_parse_svg_path_compact_numbers() -> None:
    assert parse_svg_path("M1.5-2.5.5.5")[:2] == [(1.5, -2.5), (0.5, 0.5)]


def test_parse_svg_path_truncated_raises() -> None:
    with pytest.raises(ValueError, match="truncado"):
        parse_svg_path("M1")


def test_resample_point_count_and_endpoints() -> None:
    short = resample([(0, 0), (10, 0)])
    assert len(short) == 12
    long = resample([(0, 0), (900, 0)])
    assert len(long) == 30
    assert long[0] == (0, 0) and long[-1] == (900, 0)
    xs = [p[0] for p in long]
    assert xs == sorted(xs)
    assert resample([(5, 5), (5, 5)]) == [(5, 5)] * 12


def test_catmull_rom_passes_through_points() -> None:
    src = [(0.0, 0.0), (100.0, 50.0), (200.0, 0.0)]
    smooth = catmull_rom(src)
    assert smooth[0] == src[0] and smooth[-1] == src[-1]
    assert any(p == pytest.approx(src[1]) for p in smooth)


def test_parse_mmah_flips_y_and_filters(tmp_path: Path) -> None:
    f = tmp_path / "graphics.txt"
    lines = [
        {"character": "一", "strokes": ["M 0 0"], "medians": [[[100, 900], [500, 900]]]},
        {"character": "二", "strokes": ["M 0 0"], "medians": [[[0, 0], [10, 10]]]},
    ]
    # el graphics.txt real es JSON compacto, una línea por carácter
    compact = (json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in lines)
    f.write_text("\n".join(compact), encoding="utf-8")
    found = parse_mmah(f, ["一"])
    assert list(found) == ["一"]
    stroke = found["一"][0]
    assert stroke[0] == [100.0, 0.0] and stroke[-1] == [500.0, 0.0]  # y' = 900 - y


def test_parse_kanjivg_scales_orders_and_skips_variants(tmp_path: Path) -> None:
    xml = """<kanjivg>
<kanji id="kvg:kanji_030a2"><g id="kvg:030a2">
<path id="kvg:030a2-s2" d="M0,0L109,0"/><path id="kvg:030a2-s1" d="M0,109L0,0"/></g></kanji>
<kanji id="kvg:kanji_030a2-Kaisho"><g><path id="kvg:030a2-Kaisho-s1" d="M1,1L2,2"/></g></kanji>
</kanjivg>"""
    f = tmp_path / "k.xml.gz"
    f.write_bytes(gzip.compress(xml.encode()))
    found = parse_kanjivg(f, ["ア"])
    assert len(found["ア"]) == 2
    assert found["ア"][0][0] == [0.0, 1024.0]  # s1 primero, escalado 1024/109
    assert found["ア"][1][-1] == [1024.0, 0.0]
