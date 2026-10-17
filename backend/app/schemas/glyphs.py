from pydantic import BaseModel

from app.models import GlyphScript


class GlyphOut(BaseModel):
    """Trazos en una caja de 1024×1024, origen arriba-izquierda, en orden de trazo."""

    char: str
    script: GlyphScript
    stroke_count: int
    strokes: list[list[list[float]]]
    source: str
