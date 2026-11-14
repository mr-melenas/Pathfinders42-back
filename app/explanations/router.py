"""
ES: Endpoints de solo lectura. Las rutas, los parámetros de consulta y las claves del JSON están en
español porque son el contrato de la API (guía del equipo); los identificadores de Python, en inglés.
EN: Read-only endpoints. Routes, query parameters and JSON keys are in Spanish because they are the
API contract (team guideline); Python identifiers are in English.
"""

import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from .index import get_index
from .web import search_web

router = APIRouter(tags=["explicaciones"])

EXPLANATIONS_PATH = Path(os.getenv("RAG_EXPLANATIONS", "data/rag/explanations.json"))
WEB_RATE_LIMIT_PER_MIN = int(os.getenv("WEB_RATE_LIMIT_PER_MIN", "10"))

_explanations: dict | None = None
_web_requests: dict[str, deque] = defaultdict(deque)


def _load_explanations() -> dict:
    """
    ES: Carga (una vez) las explicaciones precalculadas. EN: Loads (once) the precomputed explanations.
    """
    global _explanations
    if _explanations is None:
        if not EXPLANATIONS_PATH.exists():
            raise HTTPException(
                503, "No hay explicaciones generadas (ejecuta scripts/generate_explanations.py)."
            )
        _explanations = json.loads(EXPLANATIONS_PATH.read_text(encoding="utf-8"))
    return _explanations


def _limit_web_rate(ip: str) -> None:
    """
    ES: Límite de búsquedas web por IP y minuto (cada una puede costar dinero). EN: Per-IP web search limit per minute (each may cost money).
    """
    now, recent = time.time(), _web_requests[ip]
    while recent and now - recent[0] > 60:
        recent.popleft()
    if len(recent) >= WEB_RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "Demasiadas búsquedas web; espera un minuto.")
    recent.append(now)


@router.get("/explicaciones/{sitio_id}")
def get_explanation(sitio_id: str) -> dict:
    """
    ES: Explicación precalculada de un sitio. EN: Precomputed explanation for a site.
    """
    explanations = _load_explanations()
    if sitio_id not in explanations:
        raise HTTPException(404, f"Sin explicación para el sitio '{sitio_id}'.")
    return explanations[sitio_id]


@router.get("/buscar")
def search(
    request: Request,
    q: str = Query(..., min_length=2),
    sitio_id: str | None = None,
    tipo: str | None = None,
    n: int = Query(4, ge=1, le=10),
    fuente: Literal["documentacion", "web", "ambas"] = "documentacion",
) -> list[dict]:
    """
    ES: Busca en la documentación (corpus) y/o en internet (dominios permitidos, con caché). Cada
    resultado lleva `origen`; los de la web, además `fecha_consulta`, y no están verificados.
    EN: Searches the documentation (corpus) and/or the web (allowed domains, cached). Each result
    carries `origen`; web ones also carry `fecha_consulta` and are not verified.
    """
    results: list[dict] = []
    if fuente in ("documentacion", "ambas"):
        results += [
            {**f, "origen": "documentacion"} for f in get_index().search(q, k=n, site_id=sitio_id, kind=tipo)
        ]
    if fuente in ("web", "ambas"):
        _limit_web_rate(request.client.host if request.client else "unknown")
        try:
            results += search_web(q, n=n)
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from error
        except httpx.HTTPError as error:
            raise HTTPException(502, f"Error del proveedor de búsqueda web: {error}") from error
    return results


@router.get("/fuentes")
def list_sources() -> list[dict]:
    """
    ES: Fuentes únicas del corpus, con su URL y tipo. EN: Unique corpus sources, with URL and type.
    """
    seen: dict[str, dict] = {}
    for fragment in get_index().fragments:
        seen.setdefault(
            fragment["fuente"],
            {"fuente": fragment["fuente"], "url": fragment.get("url"), "tipo": fragment.get("tipo")},
        )
    return sorted(seen.values(), key=lambda s: s["fuente"])
