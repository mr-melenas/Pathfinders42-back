"""
ES: Búsqueda BM25 en Python puro sobre el corpus (sin modelos, sin dependencias, sin red).
"""

import json
import math
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path

# ES: Ruta del corpus (una línea JSON por fragmento).
CORPUS_PATH = Path(os.getenv("RAG_CORPUS", "data/rag/corpus.jsonl"))

# ES: Palabras vacías en español, sin tildes.
STOPWORDS = {
    "a",
    "al",
    "ante",
    "con",
    "de",
    "del",
    "e",
    "el",
    "en",
    "es",
    "la",
    "las",
    "lo",
    "los",
    "o",
    "para",
    "por",
    "que",
    "se",
    "si",
    "su",
    "sus",
    "un",
    "una",
    "y",
    "u",
    "como",
    "mas",
    "muy",
    "pero",
    "sin",
    "sobre",
    "entre",
    "este",
    "esta",
    "estos",
    "estas",
    "ese",
    "esa",
}


def tokenize(text: str) -> list[str]:
    """
    ES: Minúsculas, sin tildes, solo alfanuméricos y sin palabras vacías.
    EN: Lowercase, accent-free, alphanumeric only, stopwords removed.
    """
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return [w for w in re.findall(r"[a-z0-9]+", stripped) if len(w) > 1 and w not in STOPWORDS]


class TextIndex:
    """
    ES: Índice BM25. Cada fragmento es un dict con al menos la clave "texto".
    EN: BM25 index. Each fragment is a dict with at least the "texto" key.
    """

    def __init__(self, fragments: list[dict] | None = None, path: Path = CORPUS_PATH):
        if fragments is None:
            fragments = []
            if path.exists():
                with path.open(encoding="utf-8") as file:
                    fragments = [json.loads(line) for line in file if line.strip()]
        self.fragments = fragments
        self._term_freqs = [Counter(tokenize(f["texto"])) for f in fragments]
        self._lengths = [sum(c.values()) for c in self._term_freqs]
        self._avg_length = sum(self._lengths) / len(self._lengths) if self._lengths else 0.0
        doc_freq: Counter = Counter()
        for counts in self._term_freqs:
            doc_freq.update(counts.keys())
        total = len(fragments)
        self._idf = {t: math.log(1 + (total - d + 0.5) / (d + 0.5)) for t, d in doc_freq.items()}

    def search_positions(
        self, query: str, k: int = 4, site_id: str | None = None, kind: str | None = None
    ) -> list[tuple[int, float]]:
        """
        ES: Devuelve (posición, puntuación) de los k mejores fragmentos. `kind` filtra por "tipo";
        `site_id` excluye fragmentos de OTRO sitio concreto (los generales se mantienen).
       
        """
        query_terms = tokenize(query)
        scored: list[tuple[int, float]] = []
        for pos, fragment in enumerate(self.fragments):
            if kind and fragment.get("tipo") != kind:
                continue
            if site_id and fragment.get("sitio_id") not in (None, site_id):
                continue
            score = 0.0
            for term in query_terms:
                freq = self._term_freqs[pos].get(term, 0)
                if freq:
                    norm = freq + 1.5 * (1 - 0.75 + 0.75 * self._lengths[pos] / (self._avg_length or 1))
                    score += self._idf[term] * freq * 2.5 / norm
            if score > 0:
                scored.append((pos, score))
        scored.sort(key=lambda item: -item[1])
        return scored[:k]

    def search(
        self, query: str, k: int = 4, site_id: str | None = None, kind: str | None = None
    ) -> list[dict]:
        """
        ES: Igual que search_positions pero devuelve los fragmentos con su "puntuacion".
       
        """
        return [
            {**self.fragments[pos], "puntuacion": round(score, 3)}
            for pos, score in self.search_positions(query, k, site_id, kind)
        ]


_index: TextIndex | None = None


def get_index() -> TextIndex:
    """
    ES: Índice compartido, cargado una sola vez. 
    """
    global _index
    if _index is None:
        _index = TextIndex()
    return _index
