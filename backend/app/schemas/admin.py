import uuid
from typing import Annotated

from pydantic import BaseModel, Field

from app.models import Connotation, Gender, Script

Text = Annotated[str, Field(min_length=1, max_length=40)]


class TranslitIn(BaseModel):
    script: Script
    text: Text
    reading: Annotated[str, Field(min_length=1, max_length=120)]
    rank: Annotated[int, Field(ge=1, le=3)] = 1


class TranslitOut(TranslitIn):
    id: int
    verified: bool


class NameIn(BaseModel):
    display_name: Annotated[str, Field(min_length=1, max_length=60)]
    gender: Gender = Gender.u
    verified: bool = True
    transliterations: Annotated[list[TranslitIn], Field(min_length=1, max_length=9)]


class NameOut(BaseModel):
    id: int
    name_es: str
    display_name: str
    gender: Gender
    verified: bool
    transliterations: list[TranslitOut]
    missing_glyphs: list[str] = []  # caracteres sin trazos: el robot aún no puede escribirlos


class NamePage(BaseModel):
    items: list[NameOut]
    total: int
    page: int
    page_size: int


class VerifyIn(BaseModel):
    verified: bool = True


class SyllableIn(BaseModel):
    script: Script
    syllable_es: Annotated[str, Field(pattern=r"^[a-zñü]{1,16}$")]
    output: Annotated[str, Field(min_length=1, max_length=16)]
    reading: Annotated[str, Field(min_length=1, max_length=32)]
    meaning: Annotated[str | None, Field(max_length=120)] = None
    connotation: Connotation = Connotation.neutral
    gender_hint: Gender = Gender.u
    score: Annotated[int, Field(ge=0, le=100)] = 50


class SyllableOut(SyllableIn):
    id: int


class SyllablePage(BaseModel):
    items: list[SyllableOut]
    total: int
    page: int
    page_size: int


class PendingItem(BaseModel):
    request_id: uuid.UUID
    input_name: str
    created_at: str
    zh: dict[str, str] | None  # {"text", "pinyin"} de la primera opción
    ja: dict[str, str] | None  # {"text", "romaji"}
