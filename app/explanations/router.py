"""
ES: Endpoints. Las rutas, los parámetros de consulta y las claves del JSON están en español porque son
el contrato de la API (guía del equipo); los identificadores de Python, en inglés.
 - GET /explicaciones/{sitio_id}, /buscar, /fuentes: solo lectura (resultados precalculados / búsqueda).
 - POST /preguntar: chat ONLINE; recupera fragmentos, el LLM (Qwen por API) redacta y se valida.
"""

import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .index import get_index
from .llm import ApiGenerator, llm_configured
from .retrieval import get_retriever
from .web import cache_only_enabled, search_web
from .writer import MAX_QUESTION_CHARS, chat_input, write_explanation

router = APIRouter(tags=["explicaciones"])

EXPLANATIONS_PATH = Path(os.getenv("RAG_EXPLANATIONS", "data/rag/explanations.json"))
WEB_RATE_LIMIT_PER_MIN = int(os.getenv("WEB_RATE_LIMIT_PER_MIN", "10"))
CHAT_RATE_LIMIT_PER_MIN = int(os.getenv("CHAT_RATE_LIMIT_PER_MIN", "10"))
TRUST_PROXY = (
    os.getenv("TRUST_PROXY") == "1"
)  # ES: detrás de Render/Railway/Cloudflare... / EN: behind a proxy

_explanations: dict | None = None
_web_requests: dict[str, deque] = defaultdict(deque)
_chat_requests: dict[str, deque] = defaultdict(deque)


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


def _client_ip(request: Request) -> str:
    """
    ES: IP del cliente; con TRUST_PROXY=1 usa X-Forwarded-For (si no, la IP del proxy sería la de todos).
    EN: Client IP; with TRUST_PROXY=1 it uses X-Forwarded-For (otherwise every user shares the proxy IP).
    """
    if TRUST_PROXY and request.headers.get("x-forwarded-for"):
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _limit(bucket: dict[str, deque], ip: str, limit: int, message: str) -> None:
    now, recent = time.time(), bucket[ip]
    while recent and now - recent[0] > 60:
        recent.popleft()
    if len(recent) >= limit:
        raise HTTPException(429, message)
    recent.append(now)


def _limit_web_rate(ip: str) -> None:
    """
    ES: Límite de búsquedas web por IP y minuto (cada una puede costar dinero). EN: Per-IP web search limit per minute (each may cost money).
    """
    _limit(_web_requests, ip, WEB_RATE_LIMIT_PER_MIN, "Demasiadas búsquedas web; espera un minuto.")


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
    Con WEB_CACHE_ONLY=1 solo responde lo que esté en caché y no cuenta para el límite.
    EN: Searches the documentation (corpus) and/or the web (allowed domains, cached). Each result
    carries `origen`; web ones also carry `fecha_consulta` and are not verified.
    """
    results: list[dict] = []
    if fuente in ("documentacion", "ambas"):
        results += [
            {**f, "origen": "documentacion"} for f in get_index().search(q, k=n, site_id=sitio_id, kind=tipo)
        ]
    if fuente in ("web", "ambas"):
        if not cache_only_enabled():  # ES: servir caché no cuesta nada / EN: cache hits cost nothing
            _limit_web_rate(_client_ip(request))
        try:
            results += search_web(q, n=n)
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from error
        except httpx.HTTPError as error:
            raise HTTPException(502, f"Error del proveedor de búsqueda web: {error}") from error
    return results


class Question(BaseModel):
    pregunta: str = Field(..., min_length=2, max_length=MAX_QUESTION_CHARS)
    sitio_id: str | None = None
    fuente: Literal["documentacion", "web", "ambas"] = "documentacion"


def get_generator():
    """
    ES: Generador del LLM (se sustituye en las pruebas). EN: LLM generator (replaced in tests).
    """
    return ApiGenerator()


@router.post("/preguntar")
def ask(body: Question, request: Request) -> dict:
    """
    ES: Chat online. Recupera fragmentos (y web si `fuente` lo pide), el LLM responde en español y se
    validan cifras y citas; si falla dos veces, responde con la plantilla determinista.
    EN: Online chat. Retrieves fragments (and web if `fuente` asks), the LLM answers in Spanish, figures
    and citations are validated; after two failures it answers with the deterministic template.
    """
    if not llm_configured():
        raise HTTPException(503, "LLM no configurado (LLM_BASE_URL, LLM_API_KEY, MODEL_LLM).")
    ip = _client_ip(request)
    _limit(_chat_requests, ip, CHAT_RATE_LIMIT_PER_MIN, "Demasiadas preguntas; espera un minuto.")
    use_web = body.fuente in ("web", "ambas")
    if use_web and not cache_only_enabled():
        _limit_web_rate(ip)
    explanation = None
    if body.sitio_id:
        explanation = _load_explanations().get(body.sitio_id)
        if explanation is None:
            raise HTTPException(404, f"Sin explicación para el sitio '{body.sitio_id}'.")
    data, query, template, web_query = chat_input(body.pregunta, explanation)
    try:
        result = write_explanation(
            data,
            query,
            get_retriever(),
            get_generator(),
            template,
            use_web=use_web,
            web_query=web_query,
            site_id=body.sitio_id,
            strict_web=False,
        )
    except httpx.HTTPError as error:
        raise HTTPException(502, f"Error del LLM: {error}") from error
    answer = {
        "respuesta": result["texto_llm"],
        "texto_origen": result["texto_origen"],
        "fragmentos_usados": result["fragmentos_usados"],
    }
    if "aviso" in result:
        answer["aviso"] = result["aviso"]
    return answer


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
