"""
ES: Pruebas del validador de cifras. EN: Figure validator tests.
"""

from app.explanations.validator import invalid_citations, invalid_figures

DATA = {"distancia": 0.229, "similitud": 0.771, "brechas": {"brecha_ts_media": -76.0}, "n": 3}
FRAGMENTS = ["Estudio de 2022 sobre el sitio."]


def test_accepts_present_figures_and_roundings():
    text = "Similitud 0,77 y distancia 0.229; brecha de 76 °C en 3 capas, según el estudio de 2022."
    assert invalid_figures(text, DATA, FRAGMENTS) == []


def test_detects_invented_figures():
    assert invalid_figures("La distancia es 0.5 y la brecha 120 °C.", DATA, FRAGMENTS) == [0.5, 120.0]


def test_ignores_small_integers():
    assert invalid_figures("Funciona en 2 de 5 capas.", DATA) == []


def test_thousands_separator_is_not_a_false_positive():
    assert invalid_figures("Una distancia de 1.200 km.", {"d": 1200}) == []
    assert invalid_figures("Una distancia de 1.200 km.", {"d": 1.2}) == []
    assert invalid_figures("Una distancia de 1.200 km.", {"d": 5}) == [1.2]


def test_citations_are_not_figures_and_are_range_checked():
    assert invalid_figures("Según la ficha [12].", DATA) == []
    assert invalid_citations("A [1] y B [3].", 3) == []
    assert invalid_citations("A [7], B [0].", 5) == [7, 0]
