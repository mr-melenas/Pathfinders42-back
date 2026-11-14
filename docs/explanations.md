# Explicaciones internas · Internal explanations (RAG)
 
**ES:** Módulo interno para explicar por qué un lugar de la Tierra es (o no) análogo de un sitio de la
Luna o Marte. Reparto: el Random Forest (M1) + SHAP decide y puntúa; el LLM solo redacta; la API solo sirve
resultados precalculados. **EN:** Internal module that explains why an Earth location is (or is not) an
analog of a Moon/Mars site. Split: the Random Forest (M1) + SHAP decides and scores; the LLM only writes;
the API only serves precomputed results.
 
## Convenciones · Conventions
- **ES:** Identificadores de Python (variables, funciones, clases, módulos) en inglés. Rutas de la API,
  parámetros de consulta y claves del JSON en español (contrato del equipo). Comentarios y docstrings bilingües.
- **EN:** Python identifiers (variables, functions, classes, modules) in English. API routes, query
  parameters and JSON keys in Spanish (team contract). Bilingual comments and docstrings.
## Flujo offline · Offline flow (after the data freeze, Thursday 12 Nov)
1. **ES:** Exportar a `.md` en `data/rag/sources/` la bibliografía, la ficha de análogos y las notas de límites
   (`tipo = limites`) y rellenar `data/rag/sources.csv`. **EN:** Export the bibliography, analog sheet and
   limits notes (`tipo = limites`) to `.md` in `data/rag/sources/` and fill `data/rag/sources.csv`.
2. `python scripts/build_corpus.py` → `data/rag/corpus.jsonl`
3. **ES:** Con la API local levantada: `python scripts/generate_explanations.py` → `data/rag/explanations.json`.
   **EN:** With the local API running: `python scripts/generate_explanations.py` → `data/rag/explanations.json`.
4. **ES:** En Colab: `pip install -r requirements-offline.txt` y `python scripts/write_with_llm.py [--web]`
   (añade `texto_llm`, `texto_origen` y `fragmentos_usados`). Para candidatos de M1: `--candidates m1.json`.
   **EN:** In Colab: `pip install -r requirements-offline.txt` and `python scripts/write_with_llm.py [--web]`
   (adds `texto_llm`, `texto_origen` and `fragmentos_usados`). For M1 candidates: `--candidates m1.json`.
5. **ES:** Versionar `data/rag/` en el repo back. **EN:** Commit `data/rag/` to the back repo.
## Integración · Integration (`feat/explicaciones` from `dev`)
```python
from app.explanations.router import router as explanations_router

app.include_router(explanations_router, prefix="/api/v1")
```
Endpoints: `GET /explicaciones/{sitio_id}`, `GET /buscar?q=&fuente=documentacion|web|ambas`, `GET /fuentes`.
Tests: `pytest tests/`.
 
## Recuperación y validación · Retrieval and validation
- **ES:** BM25 + embeddings (BGE-M3), fusión RRF, reranker (bge-reranker-v2-m3), LLM. `validator.py` descarta
  textos con cifras ausentes de los datos o fragmentos (reintento y, si falla, plantilla). Enteros ≤ 10 permitidos.
- **EN:** BM25 + embeddings (BGE-M3), RRF fusion, reranker (bge-reranker-v2-m3), LLM. `validator.py` discards
  texts with figures missing from the data or fragments (one retry, then the template). Integers ≤ 10 allowed.
- **ES:** `MODEL_LLM` apunta a un modelo de ejemplo: cambiadlo por el elegido. **EN:** `MODEL_LLM` points to an
  example model: change it to the chosen one.
## Internet · Web search
- **ES:** `WEB_PROVIDER` (`tavily` | `brave`) y su clave (`TAVILY_API_KEY` / `BRAVE_API_KEY`); `WEB_DOMAINS`
  (por defecto nasa.gov, esa.int, usgs.gov, jaxa.jp, lpi.usra.edu, arxiv.org, doi.org); `WEB_RATE_LIMIT_PER_MIN`.
  Caché en `data/rag/web_cache.json`: versionadla y desplegad con `WEB_CACHE_ONLY=1` para que la demo no dependa
  de internet. Los adaptadores NO se han probado con red real.
- **EN:** `WEB_PROVIDER` (`tavily` | `brave`) and its key (`TAVILY_API_KEY` / `BRAVE_API_KEY`); `WEB_DOMAINS`
  (default nasa.gov, esa.int, usgs.gov, jaxa.jp, lpi.usra.edu, arxiv.org, doi.org); `WEB_RATE_LIMIT_PER_MIN`.
  Cache in `data/rag/web_cache.json`: commit it and deploy with `WEB_CACHE_ONLY=1` so the demo does not depend
  on the internet. The adapters have NOT been tested against the real network.