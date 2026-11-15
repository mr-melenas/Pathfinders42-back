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
from .writer import MAX_QUESTION_CHARS, chat_input, write_explanation

router = APIRouter(tags=["explicaciones"])

EXPLANATIONS_PATH = Path(os.getenv("RAG_EXPLANATIONS", "data/rag/explanations.json"))
CHAT_RATE_LIMIT_PER_MIN = int(os.getenv("CHAT_RATE_LIMIT_PER_MIN", "10"))
TRUST_PROXY = (
    os.getenv("TRUST_PROXY") == "1"
)  # ES: detrás de Render/Railway/Cloudflare... / EN: behind a proxy

_explanations: dict | None = None
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
    q: str = Query(..., min_length=2),
    sitio_id: str | None = None,
    tipo: str | None = None,
    n: int = Query(4, ge=1, le=10),
    fuente: Literal["documentacion"] = "documentacion",
) -> list[dict]:
    """
    ES: Busca solo en la documentación local. Cada resultado indica su origen.
    EN: Searches only the local documentation. Each result identifies its origin.
    """
    return [{**f, "origen": fuente} for f in get_index().search(q, k=n, site_id=sitio_id, kind=tipo)]


class Question(BaseModel):
    pregunta: str = Field(..., min_length=2, max_length=MAX_QUESTION_CHARS)
    sitio_id: str | None = None
    fuente: Literal["documentacion"] = "documentacion"


def get_generator():
    """
    ES: Generador del LLM (se sustituye en las pruebas). EN: LLM generator (replaced in tests).
    """
    return ApiGenerator()


def _analog(site_id: str | None, earth_id: str) -> dict:
    """
    ES: Ficha del análogo (capa analogos) con los límites de la Tierra de su cuerpo.
    EN: Analog record (analogos layer) with the Earth limits of its body.
    """
    from app.dependencias import obtener_datos

    if not site_id:
        raise HTTPException(422, "tierra_id necesita sitio_id.")
    analogs = obtener_datos().analogos
    site, record = analogs.sitio(site_id), analogs.ficha(site_id, earth_id)
    if site is None or record is None:
        raise HTTPException(404, f"{earth_id} no es pareja de {site_id}.")
    return {
        **record,
        "sitio_nombre": site["nombre"],
        "cuerpo": site["cuerpo"],
        "limites_tierra": analogs.limites(site["cuerpo"]),
    }


@router.post("/preguntar")
def ask(body: Question, request: Request) -> dict:
    """
    ES: Responde usando fragmentos de la documentación local; valida cifras y citas y, si falla dos
    veces, devuelve la plantilla determinista.
    EN: Answers using local documentation fragments, validates figures and citations, and returns the
    deterministic template after two failed attempts.
    """
    if not llm_configured():
        raise HTTPException(503, "LLM no configurado (LLM_BASE_URL, LLM_API_KEY, MODEL_LLM).")
    ip = _client_ip(request)
    _limit(_chat_requests, ip, CHAT_RATE_LIMIT_PER_MIN, "Demasiadas preguntas; espera un minuto.")
    explanation = None
    if body.sitio_id:
        explanation = _load_explanations().get(body.sitio_id)
        if explanation is None:
            raise HTTPException(404, f"Sin explicación para el sitio '{body.sitio_id}'.")
    data, query, template = chat_input(body.pregunta, explanation)
    try:
        result = write_explanation(
            data,
            query,
            get_retriever(),
            get_generator(),
            template,
            site_id=body.sitio_id,
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
