import pytest

from app.services.transliterate_ja import kana_to_romaji, transliterate_ja

REFERENCE = [
    ("Carlos", "カルロス"),
    ("Ana", "アナ"),
    ("Pablo", "パブロ"),
    ("María", "マリア"),
    ("José", "ホセ"),
    ("Juan", "フアン"),
    ("Luis", "ルイス"),
    ("Pedro", "ペドロ"),
    ("Sofía", "ソフィア"),
    ("Diego", "ディエゴ"),
    ("Miguel", "ミゲル"),
    ("Laura", "ラウラ"),
    ("Cristian", "クリスティアン"),
    ("Guillermo", "ギジェルモ"),
    ("Alejandro", "アレハンドロ"),
    ("Francisco", "フランシスコ"),
    ("Gabriel", "ガブリエル"),
    ("Eduardo", "エドゥアルド"),
    ("Fernando", "フェルナンド"),
    ("Santiago", "サンティアゴ"),
    ("Andrés", "アンドレス"),
    ("Alberto", "アルベルト"),
    ("Ricardo", "リカルド"),
    ("Manuel", "マヌエル"),
    ("Rafael", "ラファエル"),
    ("Javier", "ハビエル"),
    ("Sergio", "セルヒオ"),
    ("Isabel", "イサベル"),
    ("Patricia", "パトリシア"),
    ("Carmen", "カルメン"),
    ("Lucía", "ルシア"),
    ("Jorge", "ホルヘ"),
    ("Antonio", "アントニオ"),
    ("Enrique", "エンリケ"),
    ("Ximena", "シメナ"),
    ("Yolanda", "ヨランダ"),
    ("Mercedes", "メルセデス"),
    ("Valentina", "バレンティナ"),
    ("Martín", "マルティン"),
    ("Raúl", "ラウル"),
    ("Kevin", "ケビン"),
    ("Hugo", "ウゴ"),
    ("Héctor", "エクトル"),
    ("Joaquín", "ホアキン"),
    ("Beatriz", "ベアトリス"),
    ("Rodríguez", "ロドリゲス"),
    ("Ambros", "アンブロス"),
    ("Dolores", "ドロレス"),
    ("Muñoz", "ムニョス"),
    ("Núñez", "ヌニェス"),
    ("Chávez", "チャベス"),
    ("Wilson", "ウィルソン"),
    ("Alexander", "アレクサンデル"),
    ("Uruguay", "ウルグアイ"),
    ("Pingüino", "ピングイノ"),
]


@pytest.mark.parametrize(("name", "expected"), REFERENCE)
def test_reference_names(name: str, expected: str) -> None:
    assert transliterate_ja(name).text == expected


def test_at_least_40_reference_names() -> None:
    assert len(REFERENCE) >= 40


def test_ll_mode() -> None:
    assert transliterate_ja("Sevilla").text == "セビジャ"
    assert transliterate_ja("Sevilla", ll_mode="y").text == "セビヤ"


def test_multiple_words_use_middle_dot() -> None:
    r = transliterate_ja("Ana-María Pérez")
    assert r.text == "アナ・マリア・ペレス"
    assert r.romaji == "ana maria peresu"


@pytest.mark.parametrize(
    ("name", "romaji"),
    [
        ("Carlos", "karurosu"),
        ("Cristian", "kurisutian"),
        ("José", "hose"),
        ("Juan", "fuan"),
        ("Sofía", "sofia"),
        ("Guillermo", "gijerumo"),
        ("Pedro", "pedoro"),
        ("Muñoz", "munyosu"),
        ("Chávez", "chabesu"),
    ],
)
def test_romaji(name: str, romaji: str) -> None:
    assert transliterate_ja(name).romaji == romaji


def test_empty_and_vowelless() -> None:
    assert transliterate_ja("").text == ""
    assert transliterate_ja("Mr").text == "ムル"


def test_kana_to_romaji_digraphs() -> None:
    assert kana_to_romaji("ティファニー") == "tifani"
