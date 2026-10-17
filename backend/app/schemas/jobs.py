import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models import JobStatus, Script

PAPERS = {
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "carta": (215.9, 279.4),
    "media_carta": (139.7, 215.9),
    "oficio": (215.9, 330.0),
    "medio_oficio": (165.0, 215.9),
}


class Layout(BaseModel):
    """Disposición sobre la cartulina. Todas las medidas en milímetros, origen arriba-izquierda."""

    paper: Literal[
        "A4", "A5", "carta", "media_carta", "oficio", "medio_oficio", "custom"
    ] = "A4"
    width_mm: float | None = Field(default=None, ge=50, le=1000)  # solo papel personalizado
    height_mm: float | None = Field(default=None, ge=50, le=1000)
    landscape: bool = False
    margin_mm: float = Field(default=15, ge=0, le=100)
    char_size_mm: float = Field(default=40, ge=10, le=200)
    spacing_mm: float = Field(default=8, ge=0, le=100)
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    dip_every_chars: int = Field(default=2, ge=1, le=20)  # mojar el pincel cada N caracteres
    auto_fit: bool = True  # reduce el tamaño del carácter si el texto no cabe

    @model_validator(mode="after")
    def _custom_needs_size(self) -> "Layout":
        if self.paper == "custom" and (self.width_mm is None or self.height_mm is None):
            raise ValueError("El papel personalizado necesita ancho y alto.")
        return self

    def paper_size(self) -> tuple[float, float]:
        if self.paper == "custom":
            w, h = self.width_mm or 0.0, self.height_mm or 0.0
        else:
            w, h = PAPERS[self.paper]
        return (max(w, h), min(w, h)) if self.landscape else (w, h)


class JobCreate(BaseModel):
    request_id: uuid.UUID
    script: Script
    rank: int = Field(default=1, ge=1, le=3)
    layout: Layout = Field(default_factory=Layout)


class PathPreview(BaseModel):
    """Ruta simplificada para animar: trazos con la pluma abajo, en mm sobre la cartulina."""

    text: str
    script: Script
    layout: Layout
    paper_width_mm: float
    paper_height_mm: float
    char_size_mm: float  # tamaño efectivo (puede ser menor que el pedido si `auto_fit` actuó)
    strokes: list[list[list[float]]]
    stroke_count: int
    char_count: int
    estimated_seconds: float


class JobOut(BaseModel):
    id: uuid.UUID
    request_id: uuid.UUID
    script: Script
    text: str
    status: JobStatus
    progress: float
    layout: Layout
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    estimated_seconds: float | None = None


class JobDetail(JobOut):
    path: list[dict[str, Any]]
