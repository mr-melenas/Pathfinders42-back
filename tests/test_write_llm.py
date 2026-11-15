"""
ES: Pruebas de la lógica de redacción con un recuperador y un generador FALSOS (sin GPU ni modelos).
EN: Tests for the writing logic with a FAKE retriever and generator (no GPU, no models).
"""

import json

import pytest

from app.explanations import writer
from app.explanations.generator import explain_record
from scripts import write_with_llm as script
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
    def __init__(self):
        self.site_ids = []

    def search(self, query, k=4, pool=20, site_id=None):
        self.site_ids.append(site_id)
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


def test_empty_answer_is_retried_then_falls_back_to_template():
    generator = FakeGenerator(["", "   "])
    result = writer.write_explanation(DATA, "q", FakeRetriever(), generator, "PLANTILLA")
    assert result["texto_origen"] == "plantilla" and result["texto_llm"] == "PLANTILLA"
    assert "vacío" in generator.reminders[1]


def test_fragments_from_the_same_source_are_merged():
    a = {"fuente": "F", "url": "u", "texto": "uno"}
    b = {"fuente": "G", "url": "v", "texto": "dos"}
    c = {"fuente": "F", "url": "u", "texto": "tres"}
    merged = writer.merge_by_source([a, b, c])
    assert [f["fuente"] for f in merged] == ["F", "G"] and merged[0]["texto"] == "uno … tres"
    assert merged[1] is b and a["texto"] == "uno"


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
    assert script.site_input is writer.site_input
    assert set(data) == {"nombre", "cuerpo", "resumen", "donde_funciona", "donde_falla", "capas", "por_uso"}
    assert "Askja, Islandia" in query and "Malapert Massif" in query
    assert template.startswith(explanation["resumen"]) and "temperatura media: 122 °C más fría" in template


def test_invented_citation_triggers_retry():
    generator = FakeGenerator(["Es análogo [7].", "Es análogo [1]."])
    result = writer.write_explanation(DATA, "q", FakeRetriever(), generator, "P")
    assert result["texto_origen"] == "llm" and "[7]" in generator.reminders[1]


def test_site_id_reaches_retriever():
    retriever = FakeRetriever()
    writer.write_explanation(DATA, "q", retriever, FakeGenerator(["0.229"]), "P", site_id="s1")
    assert retriever.site_ids == ["s1"]


def test_web_failure_is_strict_offline_and_degrades_online(monkeypatch):
    def down(query, n=3):
        raise RuntimeError("no configurada")

    monkeypatch.setattr(writer, "search_web", down)
    with pytest.raises(RuntimeError):
        writer.write_explanation(DATA, "q", FakeRetriever(), FakeGenerator(["0.229"]), "P", use_web=True)
    result = writer.write_explanation(
        DATA, "q", FakeRetriever(), FakeGenerator(["0.229"]), "P", use_web=True, strict_web=False
    )
    assert result["texto_origen"] == "llm" and "aviso" in result


def test_web_query_is_short_english_and_candidate_template_is_not_json():
    explanation = explain_record(SAMPLE_RECORD)
    query = writer.web_query_for(explanation)
    assert query.startswith("Malapert Massif Moon analog") and len(query) <= 200
    assert writer.candidate_template("k", {"nombre": "X", "shap": [1, 2]}) == (
        "X: candidato a análogo; sin redacción automática disponible."
    )


def test_chat_input_with_and_without_site():
    explanation = explain_record(SAMPLE_RECORD)
    data, query, template, _web_query = writer.chat_input("  ¿Por   qué falla el clima? ", explanation)
    assert data["pregunta"] == "¿Por qué falla el clima?" and data["nombre"] == "Malapert Massif"
    assert "Malapert Massif" in query and template.startswith(explanation["resumen"])
    data, _, template, _ = writer.chat_input("hola")
    assert data == {"pregunta": "hola"} and "/buscar" in template


def test_messages_use_chat_prompt_only_with_question():
    chat = writer.build_messages({"pregunta": "x"}, [])
    explain = writer.build_messages({"nombre": "x"}, [])
    assert chat[0]["content"] == writer.CHAT_PROMPT and explain[0]["content"] == writer.EXPLAIN_PROMPT
    assert (
        "Responde a la pregunta" in chat[1]["content"]
        and "Responde a la pregunta" not in explain[1]["content"]
    )


def test_script_saves_after_each_site_and_resumes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "rag").mkdir(parents=True)
    path = tmp_path / "data" / "rag" / "explanations.json"
    record = explain_record(SAMPLE_RECORD)
    path.write_text(json.dumps({"a": record, "b": record}), encoding="utf-8")

    class Boom:
        calls = 0

        def __call__(self, data, fragments, reminder=""):
            Boom.calls += 1
            if Boom.calls == 2:
                raise KeyboardInterrupt  # simulates the process dying at site "b"
            return "Distancia 0.229."

    with pytest.raises(KeyboardInterrupt):
        script.main([], retriever=FakeRetriever(), generator=Boom())
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["a"]["texto_origen"] in ("llm", "plantilla") and "texto_origen" not in saved["b"]
    script.main(["--resume"], retriever=FakeRetriever(), generator=FakeGenerator(["Distancia 0.229."]))
    assert "texto_origen" in json.loads(path.read_text(encoding="utf-8"))["b"]
