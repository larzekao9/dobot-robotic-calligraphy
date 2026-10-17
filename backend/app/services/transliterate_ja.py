"""Transliteración fonética español → katakana (con romaji Hepburn).

Español → sílabas → (ataque, vocales, coda) → katakana. Convenciones:
- c/z suenan como s (español latinoamericano); g ante e/i y j son la fila H (j→ハ行).
- `ll` configurable: "j" → ジャ行 (por defecto), "y" → ヤ行. h es muda.
- Consonante final o de grupo recibe vocal de apoyo (l→ル, s→ス, d→ド, t→ト, n→ン…);
  en grupos como `br`/`tr` la primera consonante lleva vocal de apoyo (ブ+ラ, ト+ラ).
- No se marcan vocales largas (ー).
"""

from dataclasses import dataclass
from typing import Literal

from app.services.normalizer import clean, strip_accents
from app.services.syllabifier import split_syllable, syllabify

LLMode = Literal["j", "y"]
WORD_SEP = "・"

_VOWELS = "aiueo"
_VOWEL_KANA = dict(zip(_VOWELS, "アイウエオ", strict=True))


def _row(*kana: str) -> dict[str, str]:
    return dict(zip(_VOWELS, kana, strict=True))


_ROWS: dict[str, dict[str, str]] = {
    "k": _row("カ", "キ", "ク", "ケ", "コ"),
    "s": _row("サ", "シ", "ス", "セ", "ソ"),
    "t": _row("タ", "ティ", "トゥ", "テ", "ト"),
    "d": _row("ダ", "ディ", "ドゥ", "デ", "ド"),
    "n": _row("ナ", "ニ", "ヌ", "ネ", "ノ"),
    "h": _row("ハ", "ヒ", "フ", "ヘ", "ホ"),
    "f": _row("ファ", "フィ", "フ", "フェ", "フォ"),
    "m": _row("マ", "ミ", "ム", "メ", "モ"),
    "y": _row("ヤ", "イ", "ユ", "イェ", "ヨ"),
    "r": _row("ラ", "リ", "ル", "レ", "ロ"),
    "w": _row("ワ", "ウィ", "ウ", "ウェ", "ウォ"),
    "g": _row("ガ", "ギ", "グ", "ゲ", "ゴ"),
    "b": _row("バ", "ビ", "ブ", "ベ", "ボ"),
    "p": _row("パ", "ピ", "プ", "ペ", "ポ"),
    "ñ": _row("ニャ", "ニ", "ニュ", "ニェ", "ニョ"),
    "ch": _row("チャ", "チ", "チュ", "チェ", "チョ"),
    "ll": _row("ジャ", "ジ", "ジュ", "ジェ", "ジョ"),
}

# Letra (o dígrafo) → fila, cuando no depende de la vocal siguiente.
_ROW_OF = {
    "qu": "k", "q": "k", "k": "k", "gu": "g", "j": "h", "z": "s", "v": "b",
    "l": "r", "r": "r", "rr": "r",
}  # fmt: skip

# Consonante sin vocal propia (coda o primera consonante de un grupo).
_CODA = {
    "l": "ル", "n": "ン", "m": "ム", "s": "ス", "r": "ル", "rr": "ル", "d": "ド", "z": "ス",
    "c": "ク", "k": "ク", "q": "ク", "qu": "ク", "p": "プ", "b": "ブ", "v": "ブ", "t": "ト",
    "g": "グ", "gu": "グ", "x": "クス", "j": "フ", "f": "フ", "h": "", "ch": "チ", "ll": "ル",
    "y": "イ", "w": "ウ", "ñ": "ニ",
}  # fmt: skip


def _cv(cons: str, vowel: str, ll_mode: LLMode, initial: bool) -> str:
    if cons == "h":
        return _VOWEL_KANA[vowel]
    if cons == "x":
        return _ROWS["s"][vowel] if initial else "ク" + _ROWS["s"][vowel]
    if cons == "c":
        row = "s" if vowel in "ei" else "k"
    elif cons == "g":
        row = "h" if vowel in "ei" else "g"
    elif cons == "ll" and ll_mode == "y":
        row = "y"
    else:
        row = _ROW_OF.get(cons, cons)
    return _ROWS[row][vowel] if row in _ROWS else ""


def all_kana() -> set[str]:
    """Todos los caracteres que `transliterate_ja` puede producir."""
    chars = set("".join(_VOWEL_KANA.values())) | set("".join(_CODA.values()))
    for row in _ROWS.values():
        chars |= set("".join(row.values()))
    return chars


def transliterate_word_ja(word: str, ll_mode: LLMode = "j") -> str:
    syllables = [strip_accents(s, keep="ñü") for s in syllabify(word)]
    parts = [split_syllable(s) for s in syllables]
    out: list[str] = []
    for i, (onset, vowels, coda) in enumerate(parts):
        if not vowels:  # palabra sin vocales (p. ej. siglas)
            out += [_CODA.get(u, "") for u in onset + coda]
            continue
        for u in onset[:-1]:
            out.append(_CODA["c" if u == "ch" else u])
        if onset:
            initial = i == 0 and len(onset) == 1
            out.append(_cv(onset[-1], vowels[0], ll_mode, initial))
        else:
            out.append(_VOWEL_KANA[vowels[0]])
        out += [_VOWEL_KANA[v] for v in vowels[1:]]
        for j, u in enumerate(coda):
            last = j == len(coda) - 1
            next_onset = parts[i + 1][0] if i + 1 < len(parts) else []
            if u == "m" and last and next_onset and next_onset[0] in ("b", "p"):
                out.append("ン")
            else:
                out.append(_CODA[u])
    return "".join(out)


_ROMAJI_MONO = dict(
    zip(
        "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワンガギグゲゴ"
        "ザジズゼゾダデドバビブベボパピプペポ",
        [
            "a",
            "i",
            "u",
            "e",
            "o",
            "ka",
            "ki",
            "ku",
            "ke",
            "ko",
            "sa",
            "shi",
            "su",
            "se",
            "so",
            "ta",
            "chi",
            "tsu",
            "te",
            "to",
            "na",
            "ni",
            "nu",
            "ne",
            "no",
            "ha",
            "hi",
            "fu",
            "he",
            "ho",
            "ma",
            "mi",
            "mu",
            "me",
            "mo",
            "ya",
            "yu",
            "yo",
            "ra",
            "ri",
            "ru",
            "re",
            "ro",
            "wa",
            "n",
            "ga",
            "gi",
            "gu",
            "ge",
            "go",
            "za",
            "ji",
            "zu",
            "ze",
            "zo",
            "da",
            "de",
            "do",
            "ba",
            "bi",
            "bu",
            "be",
            "bo",
            "pa",
            "pi",
            "pu",
            "pe",
            "po",
        ],
        strict=True,
    )
)
_ROMAJI_DI = {
    "ティ": "ti", "ディ": "di", "トゥ": "tu", "ドゥ": "du", "ファ": "fa", "フィ": "fi",
    "フェ": "fe", "フォ": "fo", "ウィ": "wi", "ウェ": "we", "ウォ": "wo", "イェ": "ye",
    "ジェ": "je", "チェ": "che", "ニェ": "nye", "ニャ": "nya", "ニュ": "nyu", "ニョ": "nyo",
    "チャ": "cha", "チュ": "chu", "チョ": "cho", "ジャ": "ja", "ジュ": "ju", "ジョ": "jo",
}  # fmt: skip


def kana_to_romaji(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        pair = text[i : i + 2]
        if pair in _ROMAJI_DI:
            out.append(_ROMAJI_DI[pair])
            i += 2
        else:
            out.append(_ROMAJI_MONO.get(text[i], ""))
            i += 1
    return "".join(out)


@dataclass(frozen=True)
class JaResult:
    text: str
    romaji: str


def transliterate_ja(name: str, ll_mode: LLMode = "j") -> JaResult:
    """Nombre completo → katakana (palabras unidas con ・) y romaji (separado por espacios)."""
    kana = [transliterate_word_ja(w, ll_mode) for w in clean(name).split()]
    return JaResult(WORD_SEP.join(kana), " ".join(kana_to_romaji(k) for k in kana))
