"""
ES: Pruebas del troceado y de la construcción del corpus. EN: Chunking and corpus-building tests.
"""

import json

from app.explanations.index import TextIndex
from scripts import build_corpus


def test_split_text_overlaps_and_keeps_size_bounded():
    paragraphs = [f"Párrafo {i}. " + "palabra " * 60 for i in range(8)]
    chunks = build_corpus.split_text("\n\n".join(paragraphs))
    assert len(chunks) > 1
    assert all(len(c) <= build_corpus.CHUNK_SIZE + build_corpus.OVERLAP for c in chunks)
    assert chunks[1].startswith(chunks[0][-build_corpus.OVERLAP :])  # solape / overlap


def test_split_text_empty_and_short():
    assert build_corpus.split_text("") == []
    assert build_corpus.split_text("Un solo párrafo.") == ["Un solo párrafo."]


def test_main_builds_corpus_that_the_index_can_search(tmp_path, monkeypatch):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "limites.md").write_text(
        "La gravedad de la Tierra es un límite como análogo.\n\nLa atmósfera también.", encoding="utf-8"
    )
    (tmp_path / "sources" / "ficha.md").write_text(
        "Lofoten aparece como análogo de anortosita.", encoding="utf-8"
    )
    (tmp_path / "sources.csv").write_text(
        "archivo,fuente,url,tipo,sitio_id,analogo_id\n"
        "limites.md,Notas de límites,https://example.org/l,limites,,\n"
        "ficha.md,Ficha de análogos,,ficha,artemis-malapert-massif,lofoten_flakstadoy\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_corpus, "ROOT", tmp_path)
    build_corpus.main()

    lines = [
        json.loads(line) for line in (tmp_path / "corpus.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [item["id"] for item in lines] == ["limites.md#0", "ficha.md#0"]
    assert (
        lines[0]["tipo"] == "limites"
        and lines[0]["sitio_id"] is None
        and lines[0]["url"] == "https://example.org/l"
    )
    assert lines[1]["sitio_id"] == "artemis-malapert-massif" and lines[1]["url"] is None

    index = TextIndex(path=tmp_path / "corpus.jsonl")
    assert index.search("gravedad", kind="limites")[0]["fuente"] == "Notas de límites"


def test_long_paragraph_without_blank_lines_is_split():
    text = " ".join(f"Frase número {i} con algo de texto." for i in range(200))  # one ~7000-char paragraph
    chunks = build_corpus.split_text(text)
    assert len(chunks) > 3 and all(len(c) <= build_corpus.CHUNK_SIZE + build_corpus.OVERLAP for c in chunks)
    giant_word = build_corpus.split_text("a" * 5000)
    assert len(giant_word) > 1 and all(len(c) <= build_corpus.CHUNK_SIZE + build_corpus.OVERLAP for c in giant_word)
