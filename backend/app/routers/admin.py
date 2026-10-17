from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db import get_db
from app.errors import AppError
from app.models import (
    Connotation,
    Glyph,
    GlyphScript,
    NameDictionary,
    NameTransliteration,
    Request,
    Script,
    SyllableMap,
)
from app.schemas.admin import (
    NameIn,
    NameOut,
    NamePage,
    PendingItem,
    SyllableIn,
    SyllableOut,
    SyllablePage,
    VerifyIn,
)
from app.services.glyph_chars import SEPARATORS
from app.services.normalizer import is_valid_name, normalize, words

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])
DB = Annotated[Session, Depends(get_db)]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


# --- nombres ---------------------------------------------------------------------------------


def _name_out(db: Session, entry: NameDictionary) -> NameOut:
    missing: set[str] = set()
    for t in entry.transliterations:
        gscript = GlyphScript.zh if t.script == Script.zh else GlyphScript.ja_kana
        chars = set(t.text) - SEPARATORS
        have = set(
            db.scalars(select(Glyph.char).where(Glyph.script == gscript, Glyph.char.in_(chars)))
        )
        missing |= chars - have
    out = NameOut.model_validate(
        {
            "id": entry.id,
            "name_es": entry.name_es,
            "display_name": entry.display_name,
            "gender": entry.gender,
            "verified": entry.verified,
            "transliterations": [
                {
                    "id": t.id,
                    "script": t.script,
                    "text": t.text,
                    "reading": t.reading,
                    "rank": t.rank,
                    "verified": t.verified,
                }
                for t in sorted(entry.transliterations, key=lambda t: (t.script.value, t.rank))
            ],
            "missing_glyphs": sorted(missing),
        }
    )
    return out


def _clean_word(display_name: str) -> tuple[str, str]:
    text = display_name.strip()
    if not is_valid_name(text) or len(words(text)) != 1:
        raise AppError(
            "invalid_name", "El diccionario guarda una sola palabra, solo con letras.", 422
        )
    return text, normalize(text)


def _apply_name(db: Session, entry: NameDictionary, body: NameIn) -> None:
    display, key = _clean_word(body.display_name)
    clash = db.scalar(
        select(NameDictionary).where(NameDictionary.name_es == key, NameDictionary.id != entry.id)
    )
    if clash:
        raise AppError("name_exists", f"«{display}» ya está en el diccionario.", 409)
    entry.name_es, entry.display_name = key, display
    entry.gender, entry.verified = body.gender, body.verified
    entry.transliterations = [
        NameTransliteration(
            script=t.script,
            text=t.text.strip(),
            reading=t.reading.strip(),
            rank=t.rank,
            verified=body.verified,
        )
        for t in body.transliterations
    ]


def _name_or_404(db: Session, name_id: int) -> NameDictionary:
    entry = db.get(NameDictionary, name_id)
    if entry is None:
        raise AppError("name_not_found", "No existe ese nombre.", 404)
    return entry


@router.get("/names")
def list_names(
    db: DB,
    q: Annotated[str | None, Query(max_length=60)] = None,
    verified: bool | None = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> NamePage:
    stmt = select(NameDictionary)
    if q:
        stmt = stmt.where(NameDictionary.name_es.contains(normalize(q)))
    if verified is not None:
        stmt = stmt.where(NameDictionary.verified.is_(verified))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(NameDictionary.name_es).offset((page - 1) * page_size).limit(page_size)
    )
    return NamePage(
        items=[_name_out(db, r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.post("/names", status_code=201)
def create_name(body: NameIn, db: DB) -> NameOut:
    entry = NameDictionary(name_es="", display_name="")
    _apply_name(db, entry, body)
    db.add(entry)
    db.commit()
    return _name_out(db, entry)


@router.put("/names/{name_id}")
def update_name(name_id: int, body: NameIn, db: DB) -> NameOut:
    entry = _name_or_404(db, name_id)
    _apply_name(db, entry, body)
    db.commit()
    return _name_out(db, entry)


@router.delete("/names/{name_id}", status_code=204)
def delete_name(name_id: int, db: DB) -> None:
    db.delete(_name_or_404(db, name_id))
    db.commit()


@router.post("/names/{name_id}/verify")
def verify_name(name_id: int, body: VerifyIn, db: DB) -> NameOut:
    entry = _name_or_404(db, name_id)
    entry.verified = body.verified
    for t in entry.transliterations:
        t.verified = body.verified
    db.commit()
    return _name_out(db, entry)


# --- tabla silábica --------------------------------------------------------------------------


def _syllable_or_404(db: Session, syllable_id: int) -> SyllableMap:
    row = db.get(SyllableMap, syllable_id)
    if row is None:
        raise AppError("syllable_not_found", "No existe esa sílaba.", 404)
    return row


def _check_unique(db: Session, body: SyllableIn, own_id: int | None) -> None:
    stmt = select(SyllableMap).where(
        SyllableMap.script == body.script,
        SyllableMap.syllable_es == body.syllable_es,
        SyllableMap.output == body.output,
    )
    clash = db.scalar(stmt)
    if clash and clash.id != own_id:
        raise AppError("syllable_exists", "Esa combinación ya existe.", 409)


@router.get("/syllables")
def list_syllables(
    db: DB,
    script: Script | None = None,
    q: Annotated[str | None, Query(max_length=16)] = None,
    connotation: Connotation | None = None,
    page: Page = 1,
    page_size: PageSize = 50,
) -> SyllablePage:
    stmt = select(SyllableMap)
    if script:
        stmt = stmt.where(SyllableMap.script == script)
    if connotation:
        stmt = stmt.where(SyllableMap.connotation == connotation)
    if q:
        like = q.strip()
        stmt = stmt.where(
            or_(SyllableMap.syllable_es.contains(like), SyllableMap.output.contains(like))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(SyllableMap.script, SyllableMap.syllable_es, SyllableMap.score.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return SyllablePage(
        items=[SyllableOut.model_validate(r, from_attributes=True) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/syllables", status_code=201)
def create_syllable(body: SyllableIn, db: DB) -> SyllableOut:
    _check_unique(db, body, None)
    row = SyllableMap(**body.model_dump())
    db.add(row)
    db.commit()
    return SyllableOut.model_validate(row, from_attributes=True)


@router.put("/syllables/{syllable_id}")
def update_syllable(syllable_id: int, body: SyllableIn, db: DB) -> SyllableOut:
    row = _syllable_or_404(db, syllable_id)
    _check_unique(db, body, row.id)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return SyllableOut.model_validate(row, from_attributes=True)


@router.delete("/syllables/{syllable_id}", status_code=204)
def delete_syllable(syllable_id: int, db: DB) -> None:
    db.delete(_syllable_or_404(db, syllable_id))
    db.commit()


# --- pendientes de revisión ------------------------------------------------------------------


@router.get("/pending")
def pending_review(db: DB, limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[PendingItem]:
    """Consultas recientes con alguna palabra que aún no está en el diccionario."""
    known = set(db.scalars(select(NameDictionary.name_es)))
    out: list[PendingItem] = []
    seen: set[str] = set()
    for req in db.scalars(select(Request).order_by(Request.created_at.desc()).limit(500)):
        result = req.result_json
        key = result.get("normalized", "")
        unknown = [w for w in key.split() if w not in known]
        if not unknown or key in seen:
            continue
        seen.add(key)
        zh, ja = (result.get("zh") or [None])[0], (result.get("ja") or [None])[0]
        out.append(
            PendingItem(
                request_id=req.id,
                input_name=req.input_name,
                created_at=req.created_at.isoformat(),
                zh={"text": zh["text"], "pinyin": zh["pinyin"]} if zh else None,
                ja={"text": ja["text"], "romaji": ja["romaji"]} if ja else None,
            )
        )
        if len(out) == limit:
            break
    return out
