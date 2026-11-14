"""
ES: Recuperadores. `Bm25Retriever` (ligero, para el servidor online) y `HybridRetriever` (BM25 + embeddings
con fusión RRF y reranker; necesita sentence-transformers y es pesado). Ambos filtran por `site_id`.
EN: Retrievers. `Bm25Retriever` (light, for the online server) and `HybridRetriever` (BM25 + embeddings
with RRF fusion and a reranker; needs sentence-transformers and is heavy). Both filter by `site_id`.
"""

import os

from .index import TextIndex, get_index

EMBEDDINGS_MODEL_ID = os.getenv("MODEL_EMBEDDINGS", "BAAI/bge-m3")
RERANKER_MODEL_ID = os.getenv("MODEL_RERANKER", "BAAI/bge-reranker-v2-m3")


class Bm25Retriever:
    """
    ES: Solo BM25 (sin modelos). EN: BM25 only (no models).
    """

    def __init__(self, index: TextIndex):
        self.index = index

    def search(self, query: str, k: int = 4, pool: int = 20, site_id: str | None = None) -> list[dict]:
        return self.index.search(query, k=k, site_id=site_id)


class HybridRetriever:
    """
    ES: BM25 + embeddings (RRF) + reranker. EN: BM25 + embeddings (RRF) + reranker.
    """

    def __init__(self, index: TextIndex):
        from sentence_transformers import CrossEncoder, SentenceTransformer

        self.index = index
        self.embedder = SentenceTransformer(EMBEDDINGS_MODEL_ID)
        self.reranker = CrossEncoder(RERANKER_MODEL_ID)
        self.matrix = self.embedder.encode([f["texto"] for f in index.fragments], normalize_embeddings=True)

    def search(self, query: str, k: int = 4, pool: int = 20, site_id: str | None = None) -> list[dict]:
        if not self.index.fragments:
            return []
        # ES: filtra por sitio ANTES de rankear (los fragmentos generales se mantienen).
        # EN: filter by site BEFORE ranking (general fragments are kept).
        allowed = [
            p for p, f in enumerate(self.index.fragments) if not site_id or f.get("sitio_id") in (None, site_id)
        ]
        if not allowed:
            return []
        query_vector = self.embedder.encode([query], normalize_embeddings=True)[0]
        scores = self.matrix @ query_vector
        dense_ranking = sorted(allowed, key=lambda p: -float(scores[p]))[:pool]
        bm25_ranking = [p for p, _ in self.index.search_positions(query, k=pool, site_id=site_id)]
        fused: dict[int, float] = {}
        for ranking in (dense_ranking, bm25_ranking):  # reciprocal rank fusion
            for rank, pos in enumerate(ranking):
                fused[pos] = fused.get(pos, 0) + 1 / (60 + rank)
        candidates = sorted(fused, key=lambda p: -fused[p])[:pool]
        pairs = [(query, self.index.fragments[p]["texto"]) for p in candidates]
        reranked = sorted(zip(candidates, self.reranker.predict(pairs), strict=True), key=lambda i: -i[1])
        return [self.index.fragments[p] for p, _ in reranked[:k]]


def build_retriever(mode: str, index: TextIndex):
    """
    ES: mode = "bm25" | "hybrid". EN: mode = "bm25" | "hybrid".
    """
    return HybridRetriever(index) if mode == "hybrid" else Bm25Retriever(index)


_retriever = None


def get_retriever():
    """
    ES: Recuperador compartido del servidor (RETRIEVER=bm25 por defecto; "hybrid" para BGE-M3 + reranker).
    EN: Shared server retriever (RETRIEVER=bm25 by default; "hybrid" for BGE-M3 + reranker).
    """
    global _retriever
    if _retriever is None:
        _retriever = build_retriever(os.getenv("RETRIEVER", "bm25"), get_index())
    return _retriever
