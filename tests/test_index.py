"""
ES: Pruebas del índice BM25. EN: BM25 index tests.
"""

import json

from app.explanations.index import TextIndex, tokenize
from tests.sample_data import TEST_CORPUS


def test_tokenize_lowercases_strips_accents_and_stopwords():
    assert tokenize("La ATMÓSFERA de Marte, y el vacío!") == ["atmosfera", "marte", "vacio"]


def test_loads_corpus_from_jsonl(tmp_path):
    path = tmp_path / "corpus.jsonl"
    path.write_text(
        "\n".join(json.dumps(f, ensure_ascii=False) for f in TEST_CORPUS) + "\n\n", encoding="utf-8"
    )
    assert len(TextIndex(path=path).fragments) == 3


def test_missing_or_empty_corpus_returns_nothing(tmp_path):
    assert TextIndex(path=tmp_path / "no_existe.jsonl").search("gravedad") == []
    assert TextIndex([]).search("gravedad") == []


def test_ranks_more_relevant_fragment_first():
    results = TextIndex(TEST_CORPUS).search("cuevas lunares tubos")
    assert results[0]["id"] == "t#2"
    assert all("puntuacion" in r for r in results)


def test_accent_and_case_insensitive_matching():
    assert TextIndex(TEST_CORPUS).search("ATMOSFERA")[0]["id"] == "t#0"


def test_k_limits_results_and_unmatched_query_is_empty():
    index = TextIndex(TEST_CORPUS)
    assert len(index.search("cuevas", k=1)) == 1
    assert index.search("zzzinexistente") == []


def test_site_filter_keeps_general_fragments():
    ids = {r["id"] for r in TextIndex(TEST_CORPUS).search("cuevas", site_id="otro-sitio")}
    assert ids == {"t#1", "t#2"}
    ids = {r["id"] for r in TextIndex(TEST_CORPUS).search("cuevas", site_id="artemis-malapert-massif")}
    assert ids == {"t#2"}  # t#1 belongs to another site / pertenece a otro sitio
