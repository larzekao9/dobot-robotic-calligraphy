import csv
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Connotation,
    Gender,
    Glyph,
    GlyphScript,
    NameDictionary,
    NameTransliteration,
    Script,
    SyllableMap,
)

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def _rows(name: str, data_dir: Path) -> list[dict[str, str]]:
    with (data_dir / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def seed_names(db: Session, data_dir: Path = DATA_DIR) -> int:
    """Carga nombres con verified=False (pendientes de revisión humana). Idempotente."""
    n = 0
    for r in _rows("names_seed.csv", data_dir):
        if db.scalar(select(NameDictionary).where(NameDictionary.name_es == r["name_es"])):
            continue
        name = NameDictionary(
            name_es=r["name_es"], display_name=r["display_name"], gender=Gender(r["gender"])
        )
        name.transliterations = [
            NameTransliteration(script=Script.zh, text=r["zh_text"], reading=r["zh_reading"]),
            NameTransliteration(script=Script.ja, text=r["ja_text"], reading=r["ja_reading"]),
        ]
        db.add(name)
        n += 1
    return n


def seed_syllables(db: Session, data_dir: Path = DATA_DIR) -> int:
    n = 0
    for script in (Script.zh, Script.ja):
        for r in _rows(f"syllables_{script.value}.csv", data_dir):
            exists = db.scalar(
                select(SyllableMap).where(
                    SyllableMap.script == script,
                    SyllableMap.syllable_es == r["syllable_es"],
                    SyllableMap.output == r["output"],
                )
            )
            if exists:
                continue
            db.add(
                SyllableMap(
                    script=script,
                    syllable_es=r["syllable_es"],
                    output=r["output"],
                    reading=r["reading"],
                    meaning=r["meaning"] or None,
                    connotation=Connotation(r["connotation"]),
                    gender_hint=Gender(r["gender_hint"]),
                    score=int(r["score"]),
                )
            )
            n += 1
    return n


def seed_glyphs(db: Session, data_dir: Path = DATA_DIR) -> int:
    """Carga `data/strokes/glyphs.json` (generado por `scripts.import_strokes`). Idempotente."""
    path = data_dir / "strokes" / "glyphs.json"
    if not path.exists():
        return 0
    n = 0
    for g in json.loads(path.read_text(encoding="utf-8"))["glyphs"]:
        script = GlyphScript(g["script"])
        if db.scalar(select(Glyph).where(Glyph.script == script, Glyph.char == g["char"])):
            continue
        db.add(
            Glyph(
                char=g["char"],
                script=script,
                stroke_count=g["stroke_count"],
                strokes_json=g["strokes"],
                source=g["source"],
            )
        )
        n += 1
    return n


def run(db: Session, data_dir: Path = DATA_DIR) -> dict[str, int]:
    result = {
        "names": seed_names(db, data_dir),
        "syllables": seed_syllables(db, data_dir),
        "glyphs": seed_glyphs(db, data_dir),
    }
    db.commit()
    return result
