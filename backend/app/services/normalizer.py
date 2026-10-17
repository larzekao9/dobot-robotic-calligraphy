import re
import unicodedata

MAX_NAME_LEN = 60
MAX_WORDS = 4

_APOSTROPHES = "'’`´"
_VALID_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’\- ]+$")


def clean(text: str) -> str:
    """Minúsculas, sin apóstrofes, guiones como espacios. Conserva tildes, ñ y ü."""
    t = unicodedata.normalize("NFC", text).lower()
    for a in _APOSTROPHES:
        t = t.replace(a, "")
    return " ".join(t.replace("-", " ").split())


def strip_accents(text: str, keep: str = "ñ") -> str:
    """Quita tildes y diéresis; los caracteres de `keep` se conservan tal cual."""
    marks = {c: chr(0xE000 + i) for i, c in enumerate(keep)}
    t = unicodedata.normalize("NFC", text)
    for c, m in marks.items():
        t = t.replace(c, m)
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    for c, m in marks.items():
        t = t.replace(m, c)
    return t


def normalize(text: str) -> str:
    """Forma canónica para búsquedas: minúsculas y sin tildes (`names_dictionary.name_es`)."""
    return strip_accents(clean(text))


def words(text: str) -> list[str]:
    """Palabras limpias (con tildes) de un nombre completo."""
    return clean(text).split()


def is_valid_name(text: str) -> bool:
    """1–60 caracteres, solo letras españolas, espacios, guiones y apóstrofes; máx. 4 palabras."""
    t = text.strip()
    if not 1 <= len(t) <= MAX_NAME_LEN or not _VALID_RE.match(t):
        return False
    return 1 <= len(words(t)) <= MAX_WORDS
