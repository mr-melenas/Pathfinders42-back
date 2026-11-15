"""
ES: Pruebas del generador de explicaciones. EN: Explanation generator tests.
"""

from app.explanations.generator import explain_record
from app.explanations.index import TextIndex
from tests.sample_data import SAMPLE_RECORD, TEST_CORPUS


def test_states_and_figures():
    explanation = explain_record(SAMPLE_RECORD)
    by_layer = {layer["capa"]: layer for layer in explanation["capas"]}
    assert by_layer["anortosita"]["estado"] == "funciona"
    assert by_layer["clima"]["estado"] == "falla"
    assert by_layer["cuevas"]["estado"] == "no_decide"
    assert by_layer["anortosita"]["pareja"]["similitud"] == 0.771
    assert by_layer["clima"]["brechas"]["brecha_ts_media"] == -121.7
    assert "temperatura media: 122 °C más fría que en" in by_layer["clima"]["texto"]
    assert "Lofoten" in by_layer["anortosita"]["texto"]
    assert explanation["donde_funciona"] == ["anortosita"] and explanation["donde_falla"] == ["clima"]
    assert explanation["sin_veredicto"] == ["cuevas"]


def test_summary_and_source():
    explanation = explain_record(SAMPLE_RECORD)
    assert explanation["resumen"] == (
        "Malapert Massif (luna). funciona en 1 capa(s): anortosita. "
        "falla en 1: clima. sin veredicto por pareja en: cuevas."
    )
    assert explanation["fuente_sitio"] == {
        "fuente": "USGS ScienceBase",
        "url": "https://www.sciencebase.gov/",
    }


def test_gaps_are_split_from_other_details():
    clima = next(c for c in explain_record(SAMPLE_RECORD)["capas"] if c["capa"] == "clima")
    assert set(clima["brechas"]) == {"brecha_ts_media", "brecha_ts_min"}
    assert clima["detalles"] == {"dist_clima": 0.082}


def test_limits_only_with_corpus():
    assert explain_record(SAMPLE_RECORD)["limites"] == []
    explanation = explain_record(SAMPLE_RECORD, TextIndex(TEST_CORPUS))
    assert [limit["fuente"] for limit in explanation["limites"]] == ["Fuente de prueba"]


def test_record_without_layers_or_properties():
    explanation = explain_record({"id": "x", "nombre": "X", "cuerpo": "marte"})
    assert explanation["capas"] == []
    assert explanation["resumen"] == "X (marte). funciona en 0 capa(s). falla en 0."
    assert explanation["fuente_sitio"] == {"fuente": None, "url": None}


def test_layer_without_match_is_reported_not_crashing():
    record = {
        "id": "x",
        "nombre": "X",
        "cuerpo": "luna",
        "resumen": [{"capa": "hielo", "hay_parecido": False, "mejor": None}],
    }
    layer = explain_record(record)["capas"][0]
    assert layer["estado"] == "falla" and layer["pareja"] is None
    assert layer["texto"] == "Capa hielo: falla, sin parejas disponibles."


def test_gap_without_value_is_skipped():
    from app.explanations.generator import _layer_text

    best = {"nombre": "Askja", "distancia": 0.3}
    text = _layer_text("clima", "falla", best, {"brecha_ts_media": -12.4, "brecha_ts_min": None})
    assert "temperatura media: 12 °C más fría que en Askja" in text and "mínima" not in text
    assert "oscilación diaria: casi igual" in _layer_text("clima", "falla", best, {"brecha_osc_diaria": 0.2})
