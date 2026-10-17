import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import NameDictionary, Script
from app.schemas.names import JaOption, NameConversion, Source, ZhCharOut, ZhOption
from app.services.normalizer import MAX_NAME_LEN, MAX_WORDS, is_valid_name, normalize, words
from app.services.syllabifier import syllabify_name
from app.services.transliterate_ja import WORD_SEP as JA_SEP
from app.services.transliterate_ja import kana_to_romaji, transliterate_word_ja
from app.services.transliterate_zh import transliterate_zh

log = logging.getLogger(__name__)


def validate_name(name: str) -> None:
    """Lanza `AppError(invalid_name)` con un mensaje específico si el nombre no es válido."""
    text = name.strip()
    if not text:
        raise AppError("invalid_name", "Escribe un nombre.", 422)
    if len(text) > MAX_NAME_LEN:
        raise AppError(
            "invalid_name", f"El nombre no puede superar {MAX_NAME_LEN} caracteres.", 422
        )
    if len(words(text)) > MAX_WORDS:
        raise AppError("invalid_name", f"Usa como máximo {MAX_WORDS} palabras.", 422)
    if not is_valid_name(text):
        raise AppError(
            "invalid_name",
            "Solo se permiten letras, espacios, guiones y apóstrofes.",
            422,
        )


def _ja_word(db: Session, word: str) -> tuple[str, str, Source, bool]:
    entry = db.scalar(select(NameDictionary).where(NameDictionary.name_es == normalize(word)))
    rows = sorted(
        (t for t in entry.transliterations if t.script == Script.ja) if entry else (),
        key=lambda t: (not t.verified, t.rank),
    )
    if rows:
        return rows[0].text, rows[0].reading, "dictionary", rows[0].verified
    kana = transliterate_word_ja(word)
    return kana, kana_to_romaji(kana), "algorithm", False


def _ja_options(db: Session, name: str) -> list[JaOption]:
    parts = [_ja_word(db, w) for w in words(name)]
    if not parts:
        return []
    source: Source = "dictionary" if all(p[2] == "dictionary" for p in parts) else "algorithm"
    return [
        JaOption(
            rank=1,
            text=JA_SEP.join(p[0] for p in parts),
            romaji=" ".join(p[1] for p in parts),
            source=source,
            verified=all(p[3] for p in parts),
        )
    ]


def convert_name(db: Session, name: str) -> NameConversion:
    """Nombre (ya validado) → contrato 4.4. Diccionario primero, algoritmo después."""
    zh = transliterate_zh(db, name)
    if zh.missing:
        log.warning("zh_unmapped_units", extra={"input_name": name, "missing": zh.missing})
    return NameConversion(
        input=name.strip(),
        normalized=" ".join(normalize(w) for w in words(name)),
        syllables=[s for word in syllabify_name(name) for s in word],
        zh=[
            ZhOption(
                rank=c.rank,
                text=c.text,
                pinyin=c.pinyin,
                chars=[
                    ZhCharOut(char=ch.char, pinyin=ch.pinyin, meaning=ch.meaning) for ch in c.chars
                ],
                source=c.source,
                verified=c.verified,
            )
            for c in zh.candidates
        ],
        ja=_ja_options(db, name),
    )
