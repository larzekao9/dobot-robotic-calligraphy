import pytest

from app.services.normalizer import clean, is_valid_name, normalize, strip_accents, words


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("María", "maria"),
        ("  JOSÉ   Luis ", "jose luis"),
        ("Ñandú", "ñandu"),
        ("Núñez", "nuñez"),
        ("Pingüino", "pinguino"),
        ("O'Higgins", "ohiggins"),
        ("Ana-María", "ana maria"),
        ("Mari\u0301a", "maria"),  # í descompuesta (NFD)
    ],
)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_clean_keeps_accents_and_enye() -> None:
    assert clean("  ÁNGEL  Muñoz ") == "ángel muñoz"


def test_strip_accents_keeps_enye() -> None:
    assert strip_accents("niño") == "niño"
    assert strip_accents("canción") == "cancion"


def test_words() -> None:
    assert words("Juan  Carlos-Pérez") == ["juan", "carlos", "pérez"]


@pytest.mark.parametrize("name", ["Ana", "José Luis", "Ana-María", "O'Higgins", "Núñez Peña", "a"])
def test_valid_names(name: str) -> None:
    assert is_valid_name(name)


@pytest.mark.parametrize(
    "name",
    ["", "   ", "Ana123", "Juan!", "a b c d e", "x" * 61, "李明", "Ana_Maria", "<script>"],
)
def test_invalid_names(name: str) -> None:
    assert not is_valid_name(name)
