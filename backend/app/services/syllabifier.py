"""Silabeo del español (reglas ortográficas de la RAE).

Conserva las tildes de la entrada. Decisiones:
- `ch`, `ll`, `rr` y los `qu`/`gu` ante e/i se tratan como una sola consonante.
- `y` es vocal solo al final de palabra (`Rey`, `Uruguay`).
- Grupos inseparables: pr pl br bl fr fl gr gl cr cl kr kl tr dr. `tl` se separa (at-las).
"""

import unicodedata

from app.services.normalizer import clean

_STRONG = set("aeoáéó")
_WEAK = set("iuü")
_ACCENTED_WEAK = set("íú")
_VOWELS = _STRONG | _WEAK | _ACCENTED_WEAK
_INSEPARABLE_FIRST = set("pbfgcktd")
_Token = tuple[bool, str]  # (es_vocal, texto)


def tokenize(word: str) -> list[_Token]:
    toks: list[_Token] = []
    i, n = 0, len(word)
    while i < n:
        c = word[i]
        if (
            word[i : i + 2] in ("ch", "ll", "rr")
            or c in "qg"
            and word[i + 1 : i + 2] == "u"
            and word[i + 2 : i + 3] in tuple("eéií")
        ):
            toks.append((False, word[i : i + 2]))
            i += 2
        else:
            is_vowel = c in _VOWELS or (c == "y" and i == n - 1)
            toks.append((is_vowel, c))
            i += 1
    return toks


def _is_hiatus(a: str, b: str) -> bool:
    return (a in _STRONG and b in _STRONG) or a in _ACCENTED_WEAK or b in _ACCENTED_WEAK


def _inseparable(c1: str, c2: str) -> bool:
    if c2 == "r":
        return c1 in _INSEPARABLE_FIRST
    return c2 == "l" and c1 in _INSEPARABLE_FIRST - {"t", "d"}


def _split_cluster(cluster: list[str]) -> tuple[list[str], list[str]]:
    """Reparte consonantes entre dos núcleos: (coda de la anterior, ataque de la siguiente)."""
    n = len(cluster)
    if n <= 1:
        return [], cluster
    k = n - 2 if _inseparable(cluster[-2], cluster[-1]) else n - 1
    return cluster[:k], cluster[k:]


def syllabify(word: str) -> list[str]:
    """Separa una palabra en sílabas. `María` → ['ma', 'rí', 'a']."""
    w = unicodedata.normalize("NFC", word).lower().strip()
    nuclei: list[list[str]] = []
    clusters: list[list[str]] = [
        []
    ]  # clusters[i] va antes del núcleo i; el último es la coda final
    for is_vowel, text in tokenize(w):
        if not is_vowel:
            clusters[-1].append(text)
        elif not clusters[-1] and nuclei and not _is_hiatus(nuclei[-1][-1], text):
            nuclei[-1].append(text)
        else:
            nuclei.append([text])
            clusters.append([])
    if not nuclei:
        return [w] if w else []

    out: list[str] = []
    onset = clusters[0]
    for i, nucleus in enumerate(nuclei):
        if i < len(nuclei) - 1:
            coda, next_onset = _split_cluster(clusters[i + 1])
        else:
            coda, next_onset = clusters[i + 1], []
        out.append("".join(onset + nucleus + coda))
        onset = next_onset
    return out


def syllabify_name(name: str) -> list[list[str]]:
    """Silabea cada palabra de un nombre completo."""
    return [syllabify(w) for w in clean(name).split()]


def split_syllable(syllable: str) -> tuple[list[str], list[str], list[str]]:
    """Sílaba (con ü sin plegar) → (ataque, vocales, coda), con ü→u e y vocálica→i."""
    onset: list[str] = []
    vowels: list[str] = []
    coda: list[str] = []
    for is_vowel, text in tokenize(syllable):
        if is_vowel:
            vowels.append({"ü": "u", "y": "i"}.get(text, text))
        else:
            (coda if vowels else onset).append(text)
    return onset, vowels, coda
