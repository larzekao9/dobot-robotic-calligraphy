from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GlyphScript, NameTransliteration, Script, SyllableMap
from app.services.transliterate_ja import all_kana

# Separadores entre palabras: se omiten al escribir, no tienen trazos.
SEPARATORS = {"·", "・", " "}


def required_chars(db: Session) -> dict[GlyphScript, set[str]]:
    """Todos los caracteres que el sistema puede emitir y que necesitan trazos."""
    zh: set[str] = set()
    ja: set[str] = set(all_kana())
    for script, output in db.execute(select(SyllableMap.script, SyllableMap.output)):
        (zh if script == Script.zh else ja).update(output)
    for script, text in db.execute(select(NameTransliteration.script, NameTransliteration.text)):
        (zh if script == Script.zh else ja).update(text)
    return {
        GlyphScript.zh: zh - SEPARATORS,
        GlyphScript.ja_kana: ja - SEPARATORS,
    }
