import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Gender(str, enum.Enum):
    m = "m"
    f = "f"
    u = "u"


class Script(str, enum.Enum):
    zh = "zh"
    ja = "ja"


class ZhVariant(str, enum.Enum):
    simplified = "simplified"
    traditional = "traditional"


class GlyphScript(str, enum.Enum):
    zh = "zh"
    ja_kana = "ja_kana"
    ja_kanji = "ja_kanji"


class Connotation(str, enum.Enum):
    positive = "positive"
    neutral = "neutral"
    avoid = "avoid"


class JobStatus(str, enum.Enum):
    draft = "draft"
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class NameDictionary(Base):
    __tablename__ = "names_dictionary"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_es: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    gender: Mapped[Gender] = mapped_column(Enum(Gender), default=Gender.u)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    transliterations: Mapped[list["NameTransliteration"]] = relationship(
        back_populates="name", cascade="all, delete-orphan"
    )


class NameTransliteration(Base):
    __tablename__ = "name_transliterations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_id: Mapped[int] = mapped_column(ForeignKey("names_dictionary.id", ondelete="CASCADE"))
    script: Mapped[Script] = mapped_column(Enum(Script))
    zh_variant: Mapped[ZhVariant | None] = mapped_column(Enum(ZhVariant), nullable=True)  # solo para zh
    text: Mapped[str] = mapped_column(String(80))
    reading: Mapped[str] = mapped_column(String(120))
    rank: Mapped[int] = mapped_column(Integer, default=1)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    name: Mapped[NameDictionary] = relationship(back_populates="transliterations")


class SyllableMap(Base):
    __tablename__ = "syllable_map"
    __table_args__ = (Index("ix_syllable_map_script_syllable", "script", "syllable_es"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    script: Mapped[Script] = mapped_column(Enum(Script))
    zh_variant: Mapped[ZhVariant | None] = mapped_column(Enum(ZhVariant), nullable=True)  # solo para zh
    syllable_es: Mapped[str] = mapped_column(String(16))
    output: Mapped[str] = mapped_column(String(16))
    output_trad: Mapped[str | None] = mapped_column(String(16), nullable=True)  # tradicional (si difiere)
    reading: Mapped[str] = mapped_column(String(32))
    meaning: Mapped[str | None] = mapped_column(String(120), nullable=True)
    connotation: Mapped[Connotation] = mapped_column(Enum(Connotation), default=Connotation.neutral)
    gender_hint: Mapped[Gender] = mapped_column(Enum(Gender), default=Gender.u)
    score: Mapped[int] = mapped_column(Integer, default=50)


class Glyph(Base):
    __tablename__ = "glyphs"
    __table_args__ = (UniqueConstraint("script", "char", name="uq_glyphs_script_char"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    char: Mapped[str] = mapped_column(String(4))
    script: Mapped[GlyphScript] = mapped_column(Enum(GlyphScript))
    stroke_count: Mapped[int] = mapped_column(Integer)
    strokes_json: Mapped[Any] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(Text)


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    input_name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    result_json: Mapped[Any] = mapped_column(JSON)
    locale: Mapped[str] = mapped_column(String(16), default="es")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_created_at", "status", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("requests.id"))
    script: Mapped[Script] = mapped_column(Enum(Script))
    text: Mapped[str] = mapped_column(String(80))
    layout_json: Mapped[Any] = mapped_column(JSON)
    path_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.draft)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("requests.id"))
    chosen_rank: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
