"""Genera `data/strokes/glyphs.json` con los trazos de todos los caracteres que el sistema emite.

Uso (desde `backend/`, con la base migrada y con seeds):
    python -m scripts.import_strokes            # usa las fuentes en data/strokes/raw/
    python -m scripts.import_strokes --download # las descarga primero

Luego `python -m app.seeds` carga `glyphs.json` en la tabla `glyphs`.
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from app.db import SessionLocal
from app.models import GlyphScript
from app.seeds import DATA_DIR
from app.services.glyph_chars import required_chars
from app.services.stroke_import import build_glyphs

KANJIVG_VERSION = "r20260714"
SOURCES = {
    "graphics.txt": "https://raw.githubusercontent.com/skishore/makemeahanzi/master/graphics.txt",
    "kanjivg.xml.gz": (
        f"https://github.com/KanjiVG/kanjivg/releases/download/{KANJIVG_VERSION}/"
        f"kanjivg-{KANJIVG_VERSION[1:]}.xml.gz"
    ),
}


def download(raw_dir: Path, force: bool) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        target = raw_dir / name
        if target.exists() and not force:
            continue
        print(f"descargando {url}")
        urllib.request.urlretrieve(url, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="descarga las fuentes")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()

    raw_dir = args.data_dir / "strokes" / "raw"
    if args.download or not all((raw_dir / n).exists() for n in SOURCES):
        download(raw_dir, force=args.download)

    with SessionLocal() as db:
        required = required_chars(db)
    glyphs, missing = build_glyphs(
        required[GlyphScript.zh],
        required[GlyphScript.ja_kana],
        raw_dir / "graphics.txt",
        raw_dir / "kanjivg.xml.gz",
        KANJIVG_VERSION,
    )
    out = args.data_dir / "strokes" / "glyphs.json"
    out.write_text(json.dumps({"glyphs": glyphs}, ensure_ascii=False, separators=(",", ":")))
    print(f"{len(glyphs)} glifos escritos en {out}")
    if missing:
        print(f"SIN TRAZOS: {''.join(sorted(missing))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
