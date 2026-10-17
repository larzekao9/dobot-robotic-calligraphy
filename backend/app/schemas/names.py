import uuid
from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["dictionary", "algorithm"]


class ConvertRequest(BaseModel):
    name: str = Field(
        max_length=1000
    )  # la validación fina (60 caracteres, 4 palabras) es del servicio
    locale: str = Field(default="es", max_length=16)


class ZhCharOut(BaseModel):
    char: str
    pinyin: str
    meaning: str | None


class ZhOption(BaseModel):
    rank: int
    text: str
    pinyin: str
    chars: list[ZhCharOut]
    source: Source
    verified: bool = False


class JaOption(BaseModel):
    rank: int
    text: str
    romaji: str
    source: Source
    verified: bool = False


class NameConversion(BaseModel):
    """Contrato de salida de la sección 4.4 del plan."""

    input: str
    normalized: str
    syllables: list[str]
    zh: list[ZhOption]
    ja: list[JaOption]


class ConvertResponse(NameConversion):
    request_id: uuid.UUID
