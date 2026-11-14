"""
ES: Búsqueda en internet restringida a dominios fiables, con caché en disco.
 - Solo se aceptan resultados de WEB_DOMAINS (el proveedor puede ignorar el filtro, así que se re-filtra).
 - La caché evita depender de internet en la demo; con WEB_CACHE_ONLY=1 nunca sale a la red.
 - El texto web NO está verificado: siempre se muestra con su URL y fecha de consulta.
 - Proveedor: WEB_PROVIDER = tavily | brave, con TAVILY_API_KEY o BRAVE_API_KEY.

EN: Web search restricted to trusted domains, with an on-disk cache.
 - Only results from WEB_DOMAINS are accepted (the provider may ignore the filter, so we re-filter).
 - The cache keeps the demo independent of the internet; with WEB_CACHE_ONLY=1 it never goes online.
 - Web text is NOT verified: it is always shown with its URL and query date.
 - Provider: WEB_PROVIDER = tavily | brave, with TAVILY_API_KEY or BRAVE_API_KEY.
"""

import json
import os
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .index import tokenize

ALLOWED_DOMAINS = tuple(
    d.strip()
    for d in os.getenv(
        "WEB_DOMAINS", "nasa.gov,esa.int,usgs.gov,jaxa.jp,lpi.usra.edu,arxiv.org,doi.org"
    ).split(",")
    if d.strip()
)
CACHE_PATH = Path(os.getenv("WEB_CACHE", "data/rag/web_cache.json"))
TTL_SECONDS = int(os.getenv("WEB_TTL_HOURS", "168")) * 3600
MAX_CHARS = 600


def _domain_allowed(url: str, domains) -> bool:
    """
    ES: ¿El host de la URL es uno de los dominios (o un subdominio)? EN: Is the URL host one of the domains (or a subdomain)?
    """
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in domains)


def _tavily(query: str, count: int, domains) -> list[dict]:
    """
    ES: Adaptador de Tavily; devuelve dicts {title, url, text}. EN: Tavily adapter; returns {title, url, text} dicts.
    """
    response = httpx.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"},
        json={"query": query, "max_results": count, "include_domains": list(domains)},
        timeout=20,
    )
    response.raise_for_status()
    return [
        {"title": r.get("title", ""), "url": r["url"], "text": r.get("content", "")}
        for r in response.json().get("results", [])
    ]


def _brave(query: str, count: int, domains) -> list[dict]:
    """
    ES: Adaptador de Brave (filtra por dominio con site:). EN: Brave adapter (filters by domain with site:).
    """
    scoped_query = f"{query} ({' OR '.join(f'site:{d}' for d in domains)})"
    response = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": scoped_query, "count": count},
        headers={"X-Subscription-Token": os.environ["BRAVE_API_KEY"], "Accept": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    return [
        {"title": r.get("title", ""), "url": r["url"], "text": r.get("description", "")}
        for r in response.json().get("web", {}).get("results", [])
    ]


def provider_configured() -> bool:
    """
    ES: ¿Hay proveedor y clave configurados? EN: Are a provider and its key configured?
    """
    provider = os.getenv("WEB_PROVIDER", "")
    return (provider == "tavily" and bool(os.getenv("TAVILY_API_KEY"))) or (
        provider == "brave" and bool(os.getenv("BRAVE_API_KEY"))
    )


def _pick_provider():
    if not provider_configured():
        raise RuntimeError("Búsqueda web no configurada (WEB_PROVIDER y su clave de API).")
    return _tavily if os.environ["WEB_PROVIDER"] == "tavily" else _brave


def _read_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def search_web(
    query: str,
    n: int = 3,
    provider=None,
    domains=ALLOWED_DOMAINS,
    cache_path: Path | None = None,
    cache_only: bool | None = None,
) -> list[dict]:
    """
    ES: Busca en internet (dominios permitidos) usando antes la caché. `provider` permite inyectar un
    proveedor falso en las pruebas. Devuelve dicts con las claves del contrato (fuente, url, texto...).
    EN: Searches the web (allowed domains), checking the cache first. `provider` lets tests inject a
    fake provider. Returns dicts with the contract keys (fuente, url, texto...).
    """
    cache_path = cache_path or CACHE_PATH
    if cache_only is None:
        cache_only = os.getenv("WEB_CACHE_ONLY") == "1"
    key = " ".join(tokenize(query))
    cache = _read_cache(cache_path)
    entry = cache.get(key)
    if entry and (cache_only or time.time() - entry["ts"] < TTL_SECONDS):
        return entry["resultados"][:n]
    if cache_only:
        return []
    raw_results = (provider or _pick_provider())(query, n * 2, domains)
    today = date.today().isoformat()
    results = [
        {
            "fuente": r["title"] or r["url"],
            "url": r["url"],
            "texto": r["text"][:MAX_CHARS],
            "tipo": "web",
            "origen": "web",
            "fecha_consulta": today,
        }
        for r in raw_results
        if r.get("text") and _domain_allowed(r["url"], domains)
    ][:n]
    cache[key] = {"ts": time.time(), "resultados": results}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return results
