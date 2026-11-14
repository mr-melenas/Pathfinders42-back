"""
ES: Pruebas del cliente LLM (HTTP falso) y de los recuperadores. EN: LLM client (fake HTTP) and retriever tests.
"""

import pytest

from app.explanations import llm
from app.explanations.index import TextIndex
from app.explanations.retrieval import Bm25Retriever, build_retriever
from tests.sample_data import TEST_CORPUS


class Resp:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


def test_strip_thinking():
    assert llm.strip_thinking("<think>razono\nmucho</think>\nRespuesta.") == "Respuesta."
    assert llm.strip_thinking("<think>sin cerrar") == ""
    assert llm.strip_thinking("Normal.") == "Normal."


def test_chat_completion_payload_and_thinking_flag(monkeypatch):
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        return Resp("<think>x</think>Hola.")

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    monkeypatch.setenv("LLM_BASE_URL", "https://host/v1/")
    monkeypatch.setenv("LLM_API_KEY", "clave")
    monkeypatch.setenv("MODEL_LLM", "Qwen/Qwen3-8B")
    assert llm.chat_completion([{"role": "user", "content": "x"}]) == "Hola."
    assert sent["url"] == "https://host/v1/chat/completions"
    assert sent["headers"]["Authorization"] == "Bearer clave"
    assert sent["body"]["model"] == "Qwen/Qwen3-8B" and sent["body"]["temperature"] == 0
    assert sent["body"]["chat_template_kwargs"] == {"enable_thinking": False}
    monkeypatch.setenv("LLM_DISABLE_THINKING", "0")
    llm.chat_completion([])
    assert "chat_template_kwargs" not in sent["body"]


def test_llm_configured(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    assert llm.llm_configured() is False
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    assert llm.llm_configured() is True


def test_bm25_retriever_filters_by_site():
    retriever = Bm25Retriever(TextIndex(TEST_CORPUS))
    assert {r["id"] for r in retriever.search("cuevas", site_id="otro-sitio")} == {"t#1", "t#2"}
    assert {r["id"] for r in retriever.search("cuevas", site_id="artemis-malapert-massif")} == {"t#2"}
    assert isinstance(build_retriever("bm25", TextIndex(TEST_CORPUS)), Bm25Retriever)


def test_hybrid_retriever_filters_site_before_ranking():
    pytest.importorskip("numpy")
    import numpy as np

    from app.explanations.retrieval import HybridRetriever

    class Embedder:
        def encode(self, texts, normalize_embeddings=True):
            return np.array([[1.0, 0.0] for _ in texts])

    class Reranker:
        def predict(self, pairs):
            return [1.0] * len(pairs)

    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever.index, retriever.embedder, retriever.reranker = TextIndex(TEST_CORPUS), Embedder(), Reranker()
    retriever.matrix = retriever.embedder.encode(TEST_CORPUS)
    ids = {r["id"] for r in retriever.search("cuevas", k=5, site_id="artemis-malapert-massif")}
    assert "t#1" not in ids and "t#2" in ids
