"""
ES: Pruebas de la lógica de redacción con un recuperador y un generador FALSOS (sin GPU ni modelos).
EN: Tests for the writing logic with a FAKE retriever and generator (no GPU, no models).
"""

from app.explanations.generator import explain_record
from scripts import write_with_llm as writer
from tests.sample_data import SAMPLE_RECORD

DOC_FRAGMENT = {
    "fuente": "Ficha de análogos",
    "url": None,
    "texto": "Lofoten es análogo verificado.",
    "tipo": "ficha",
}
WEB_FRAGMENT = {
    "fuente": "NASA (prueba)",
    "url": "https://www.nasa.gov/x",
    "texto": "El estudio midió 42 grados.",
    "tipo": "web",
    "origen": "web",
}
DATA = {"nombre": "Malapert Massif", "distancia": 0.229}


class FakeRetriever:
    def search(self, query, k=4, pool=20):
        return [DOC_FRAGMENT]


class FakeGenerator:
    def __init__(self, outputs):
        self.outputs, self.reminders, self.fragments = list(outputs), [], []

    def __call__(self, data, fragments, reminder=""):
        self.reminders.append(reminder)
        self.fragments.append(fragments)
        return self.outputs.pop(0)


def test_valid_text_is_used_on_first_try():
    generator = FakeGenerator(["La distancia es 0.229 según la ficha [1]."])
    result = writer.write_explanation(DATA, "q", FakeRetriever(), generator, "PLANTILLA")
    assert result["texto_origen"] == "llm" and result["texto_llm"].startswith("La distancia")
    assert result["fragmentos_usados"] == [
        {"fuente": "Ficha de análogos", "url": None, "origen": "documentacion"}
    ]
    assert len(generator.reminders) == 1


def test_invented_figure_triggers_one_retry_then_accepts_valid_text():
    generator = FakeGenerator(["La distancia es 0.5.", "La distancia es 0.229."])
    result = writer.write_explanation(DATA, "q", FakeRetriever(), generator, "PLANTILLA")
    assert result["texto_origen"] == "llm" and result["texto_llm"] == "La distancia es 0.229."
    assert generator.reminders[0] == "" and "0.5" in generator.reminders[1]


def test_two_invalid_attempts_fall_back_to_template():
    generator = FakeGenerator(["Vale 0.5.", "Vale 0.7."])
    result = writer.write_explanation(DATA, "q", FakeRetriever(), generator, "PLANTILLA")
    assert result == {"texto_llm": "PLANTILLA", "texto_origen": "plantilla", "fragmentos_usados": []}
    assert generator.outputs == []  # exactly two attempts / exactamente dos intentos


def test_web_fragments_are_added_and_count_as_valid_input(monkeypatch):
    monkeypatch.setattr(writer, "search_web", lambda query, n=3: [WEB_FRAGMENT])
    generator = FakeGenerator(["El estudio midió 42 grados [2]."])  # 42 only exists in the web fragment
    result = writer.write_explanation(DATA, "q", FakeRetriever(), generator, "PLANTILLA", use_web=True)
    assert result["texto_origen"] == "llm"
    assert [f["origen"] for f in result["fragmentos_usados"]] == ["documentacion", "web"]
    assert generator.fragments[0][-1] is WEB_FRAGMENT


def test_web_is_not_queried_without_flag(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("web must not be queried / no se debe consultar la web")

    monkeypatch.setattr(writer, "search_web", boom)
    generator = FakeGenerator(["Distancia 0.229."])
    assert writer.write_explanation(DATA, "q", FakeRetriever(), generator, "P")["texto_origen"] == "llm"


def test_site_input_builds_data_query_and_template():
    explanation = explain_record(SAMPLE_RECORD)
    data, query, template = writer.site_input(explanation)
    assert set(data) == {"nombre", "cuerpo", "resumen", "donde_funciona", "donde_falla", "capas"}
    assert "Askja, Islandia" in query and "Malapert Massif" in query
    assert template.startswith(explanation["resumen"]) and "brecha ts media: -121.7 °C" in template
