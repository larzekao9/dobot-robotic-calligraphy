import pytest

from app.services.syllabifier import syllabify, syllabify_name

CASES = [
    # hiatos y diptongos
    ("María", "ma-rí-a"),
    ("Sofía", "so-fí-a"),
    ("Lucía", "lu-cí-a"),
    ("Rocío", "ro-cí-o"),
    ("Raúl", "ra-úl"),
    ("Saúl", "sa-úl"),
    ("Noé", "no-é"),
    ("Joel", "jo-el"),
    ("Mateo", "ma-te-o"),
    ("Leonardo", "le-o-nar-do"),
    ("Teodoro", "te-o-do-ro"),
    ("Beatriz", "be-a-triz"),
    ("Joaquín", "jo-a-quín"),
    ("Diego", "die-go"),
    ("Luis", "luis"),
    ("Ruiz", "ruiz"),
    ("Aitor", "ai-tor"),
    ("Eugenio", "eu-ge-nio"),
    ("Aurelio", "au-re-lio"),
    ("Dionisio", "dio-ni-sio"),
    ("Gabriel", "ga-briel"),
    ("Eduardo", "e-duar-do"),
    ("Guadalupe", "gua-da-lu-pe"),
    ("Mía", "mí-a"),
    ("Maximiliano", "ma-xi-mi-lia-no"),
    ("Cuauhtémoc", "cuauh-té-moc"),
    ("Uruguay", "u-ru-guay"),
    ("Rey", "rey"),
    ("Reyes", "re-yes"),
    # dígrafos y qu/gu
    ("Guillermo", "gui-ller-mo"),
    ("Raquel", "ra-quel"),
    ("Enrique", "en-ri-que"),
    ("Guerrero", "gue-rre-ro"),
    ("Rodríguez", "ro-drí-guez"),
    ("Pingüino", "pin-güi-no"),
    ("Chávez", "chá-vez"),
    ("Christian", "chris-tian"),
    ("Yolanda", "yo-lan-da"),
    ("Ainhoa", "ain-ho-a"),
    # grupos consonánticos
    ("Cristian", "cris-tian"),
    ("Pablo", "pa-blo"),
    ("Andrés", "an-drés"),
    ("Alejandro", "a-le-jan-dro"),
    ("Francisco", "fran-cis-co"),
    ("Gloria", "glo-ria"),
    ("Cristina", "cris-ti-na"),
    ("Hernández", "her-nán-dez"),
    ("González", "gon-zá-lez"),
    ("Alexander", "a-le-xan-der"),
    ("Xóchitl", "xó-chitl"),
    ("Ambros", "am-bros"),
    ("Instituto", "ins-ti-tu-to"),
    # nombres comunes
    ("Ana", "a-na"),
    ("Carlos", "car-los"),
    ("Pedro", "pe-dro"),
    ("Miguel", "mi-guel"),
    ("Juan", "juan"),
    ("José", "jo-sé"),
    ("Núñez", "nú-ñez"),
    ("Ñandú", "ñan-dú"),
    ("Sebastián", "se-bas-tián"),
    ("Valentina", "va-len-ti-na"),
    ("Isabel", "i-sa-bel"),
    ("Mercedes", "mer-ce-des"),
    ("Óscar", "ós-car"),
    ("Jesús", "je-sús"),
    ("Hugo", "hu-go"),
    ("Ahí", "a-hí"),
]


@pytest.mark.parametrize(("word", "expected"), CASES)
def test_syllabify(word: str, expected: str) -> None:
    assert "-".join(syllabify(word)) == expected


def test_at_least_50_cases() -> None:
    assert len(CASES) >= 50


def test_case_insensitive_and_nfd() -> None:
    assert syllabify("MARÍA") == ["ma", "rí", "a"]
    assert syllabify("María") == ["ma", "rí", "a"]


def test_edge_cases() -> None:
    assert syllabify("") == []
    assert syllabify("mr") == ["mr"]


def test_syllabify_name() -> None:
    assert syllabify_name("Ana-María Pérez") == [["a", "na"], ["ma", "rí", "a"], ["pé", "rez"]]
