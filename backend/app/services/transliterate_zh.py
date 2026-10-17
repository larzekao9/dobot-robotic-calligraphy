"""Transliteración fonética español → hanzi (mandarín).

Orden de prioridad por palabra: diccionario curado → algoritmo silábico.
El algoritmo descompone cada sílaba en unidades fonéticas que existen en `syllable_map`
(`ma`, `ri`, `an`, consonantes sueltas `s`, `l`…), descarta los caracteres `avoid` y devuelve
las 3 mejores combinaciones. Un grupo como `bra` se escribe 布+拉 (consonante suelta + sílaba).
"""

import heapq
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Connotation, Gender, NameDictionary, Script, SyllableMap
from app.services.normalizer import clean, normalize, strip_accents
from app.services.syllabifier import split_syllable, syllabify

WORD_SEP = "·"
MAX_ALTERNATIVES = 3
_MAX_OPTIONS_PER_UNIT = 5
_REPEAT_PENALTY = 30
_GENDER_BONUS = 10

Source = Literal["dictionary", "algorithm"]

# Consonante escrita → fila fonética de la tabla (cuando no depende de la vocal).
_ROW_OF = {"qu": "k", "q": "k", "k": "k", "gu": "g", "j": "h", "z": "s", "v": "b", "rr": "r",
           "ll": "y"}  # fmt: skip
# Consonante sin vocal propia (coda o primera consonante de un grupo) → claves de unidad.
_BARE = {"l": "l", "r": "r", "rr": "r", "d": "d", "z": "s", "s": "s", "c": "k", "k": "k",
         "q": "k", "qu": "k", "p": "p", "b": "b", "v": "b", "t": "t", "g": "g", "gu": "g",
         "f": "f", "m": "m", "n": "n", "ch": "ch"}  # fmt: skip
# ñ + vocal → unidades (ña = 尼+亚).
_ENYE = {"a": ["ni", "ya"], "e": ["nie"], "i": ["ni"], "o": ["ni", "o"], "u": ["niu"]}


@dataclass(frozen=True)
class ZhChar:
    char: str
    pinyin: str
    meaning: str | None


@dataclass(frozen=True)
class ZhCandidate:
    rank: int
    text: str
    pinyin: str
    chars: list[ZhChar]
    source: Source
    verified: bool


@dataclass
class ZhResult:
    candidates: list[ZhCandidate] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # unidades sin carácter en `syllable_map`


@dataclass(frozen=True)
class _Opt:
    output: str
    reading: str
    score: int
    gender: Gender


@dataclass(frozen=True)
class _WordCand:
    text: str
    pinyin: str
    chars: list[ZhChar]
    source: Source
    verified: bool


class _Table:
    """`syllable_map` (zh) en memoria: opciones sin `avoid` por clave, y significado por carácter."""

    def __init__(self, db: Session) -> None:
        self.options: dict[str, list[_Opt]] = {}
        self.meaning: dict[str, str | None] = {}
        rows = db.scalars(select(SyllableMap).where(SyllableMap.script == Script.zh)).all()
        for r in rows:
            self.meaning.setdefault(r.output, r.meaning)
            if r.connotation != Connotation.avoid:
                opt = _Opt(r.output, r.reading, r.score, r.gender_hint)
                self.options.setdefault(r.syllable_es, []).append(opt)
        for key, opts in self.options.items():
            opts.sort(key=lambda o: -o.score)
            self.options[key] = opts[:_MAX_OPTIONS_PER_UNIT]

    def chars(self, text: str, pinyin: str) -> list[ZhChar]:
        readings = pinyin.split()
        if len(readings) != len(text):
            readings = [""] * len(text)
        return [ZhChar(c, p, self.meaning.get(c)) for c, p in zip(text, readings, strict=True)]


def _row(cons: str, vowel: str) -> str:
    if cons == "c":
        return "s" if vowel in "ei" else "k"
    if cons == "g":
        return "h" if vowel in "ei" else "g"
    return _ROW_OF.get(cons, cons)


def _syllable_keys(
    onset: list[str], vowels: list[str], coda: list[str], initial: bool, known: set[str]
) -> list[str]:
    """Sílaba española → claves de unidades de `syllable_map`."""
    keys: list[str] = []
    for u in onset[:-1] if vowels else onset:
        keys += _bare_keys(u)
    if vowels:
        v0 = vowels[0]
        cons = onset[-1] if onset else ""
        if cons in ("", "h"):
            keys.append(v0)
        elif cons == "x":
            keys += ["s" + v0] if initial else ["k", "s" + v0]
        elif cons == "ñ":
            keys += _ENYE[v0]
        else:
            keys.append(_row(cons, v0) + v0)
        keys += vowels[1:]
        if coda and coda[0] == "n" and keys[-1] + "n" in known:  # 安, 曼, 南…
            keys[-1] += "n"
            coda = coda[1:]
    for u in coda:
        keys += _bare_keys(u)
    return keys


def _bare_keys(unit: str) -> list[str]:
    if unit == "x":
        return ["k", "s"]
    return [_BARE[unit]] if unit in _BARE else []


def _adjusted(opt: _Opt, gender: Gender | None) -> int:
    if gender in (Gender.m, Gender.f) and opt.gender in (Gender.m, Gender.f):
        return opt.score + (_GENDER_BONUS if opt.gender == gender else -_GENDER_BONUS)
    return opt.score


def _best_combinations(
    units: list[list[_Opt]], gender: Gender | None, k: int = MAX_ALTERNATIVES
) -> list[tuple[_Opt, ...]]:
    """Mejores k combinaciones (búsqueda por montículo), penalizando caracteres repetidos."""

    def pick(idx: tuple[int, ...]) -> tuple[_Opt, ...]:
        return tuple(units[i][j] for i, j in enumerate(idx))

    def score(idx: tuple[int, ...]) -> int:
        opts = pick(idx)
        chars = "".join(o.output for o in opts)
        return sum(_adjusted(o, gender) for o in opts) - _REPEAT_PENALTY * (
            len(chars) - len(set(chars))
        )

    start = (0,) * len(units)
    heap = [(-score(start), start)]
    seen = {start}
    found: list[tuple[int, tuple[int, ...]]] = []
    while heap and len(found) < 6 * k:
        neg, idx = heapq.heappop(heap)
        found.append((-neg, idx))
        for i in range(len(units)):
            if idx[i] + 1 < len(units[i]):
                nxt = idx[:i] + (idx[i] + 1,) + idx[i + 1 :]
                if nxt not in seen:
                    seen.add(nxt)
                    heapq.heappush(heap, (-score(nxt), nxt))
    found.sort(key=lambda f: -f[0])
    out: list[tuple[_Opt, ...]] = []
    texts: set[str] = set()
    for _, idx in found:
        combo = pick(idx)
        text = "".join(o.output for o in combo)
        if text not in texts:
            texts.add(text)
            out.append(combo)
        if len(out) == k:
            break
    return out


def _algorithm_word(
    word: str, table: _Table, gender: Gender | None, missing: list[str]
) -> list[_WordCand]:
    syllables = [strip_accents(s, keep="ñü") for s in syllabify(word)]
    known = set(table.options)
    keys: list[str] = []
    for i, syl in enumerate(syllables):
        onset, vowels, coda = split_syllable(syl)
        keys += _syllable_keys(onset, vowels, coda, i == 0 and len(onset) == 1, known)
    absent = [k for k in keys if k not in known]
    if absent or not keys:
        missing += [k for k in absent if k not in missing]
        return []
    out = []
    for combo in _best_combinations([table.options[k] for k in keys], gender):
        text = "".join(o.output for o in combo)
        pinyin = " ".join(o.reading for o in combo)
        out.append(_WordCand(text, pinyin, table.chars(text, pinyin), "algorithm", False))
    return out


def _dictionary_word(db: Session, word: str, table: _Table) -> list[_WordCand]:
    entry = db.scalar(select(NameDictionary).where(NameDictionary.name_es == normalize(word)))
    if entry is None:
        return []
    rows = sorted(
        (t for t in entry.transliterations if t.script == Script.zh),
        key=lambda t: (not t.verified, t.rank),
    )
    return [
        _WordCand(t.text, t.reading, table.chars(t.text, t.reading), "dictionary", t.verified)
        for t in rows
    ]


def transliterate_zh(db: Session, name: str, gender: Gender | None = None) -> ZhResult:
    """Nombre completo → hasta 3 alternativas en hanzi. Si falta alguna unidad, `missing` la lista."""
    table = _Table(db)
    result = ZhResult()
    per_word: list[list[_WordCand]] = []
    for word in clean(name).split():
        cands = _dictionary_word(db, word, table) or _algorithm_word(
            word, table, gender, result.missing
        )
        per_word.append(cands)
    if not per_word or any(not c for c in per_word):
        return result

    texts: set[str] = set()
    for k in range(max(len(c) for c in per_word)):
        picked = [c[min(k, len(c) - 1)] for c in per_word]
        text = WORD_SEP.join(p.text for p in picked)
        if text in texts:
            continue
        texts.add(text)
        result.candidates.append(
            ZhCandidate(
                rank=len(result.candidates) + 1,
                text=text,
                pinyin=" · ".join(p.pinyin for p in picked),
                chars=[ch for p in picked for ch in p.chars],
                source="dictionary"
                if all(p.source == "dictionary" for p in picked)
                else "algorithm",
                verified=all(p.verified for p in picked),
            )
        )
        if len(result.candidates) == MAX_ALTERNATIVES:
            break
    return result
