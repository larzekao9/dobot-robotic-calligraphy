from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import Glyph, GlyphScript
from app.schemas.glyphs import GlyphOut

router = APIRouter(prefix="/api/glyphs", tags=["glyphs"])


@router.get("/{script}/{char}", response_model=GlyphOut)
def get_glyph(
    script: GlyphScript,
    char: Annotated[str, Path(min_length=1, max_length=1)],
    db: Annotated[Session, Depends(get_db)],
) -> GlyphOut:
    glyph = db.scalar(select(Glyph).where(Glyph.script == script, Glyph.char == char))
    if glyph is None:
        raise AppError("glyph_not_found", f"No hay trazos para «{char}» ({script.value}).", 404)
    return GlyphOut(
        char=glyph.char,
        script=glyph.script,
        stroke_count=glyph.stroke_count,
        strokes=glyph.strokes_json,
        source=glyph.source,
    )
