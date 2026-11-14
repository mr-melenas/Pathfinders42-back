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

import html
import json
import os
import re
import threading
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
MAX_QUERY_CHARS = (
    200  # ES: Brave/Tavily limitan la query (~400) y Brave añade los site: / EN: providers cap the query
)
_cache_lock = threading.Lock()


def cache_only_enabled() -> bool:
    """
    ES: ¿WEB_CACHE_ONLY=1? (nunca sale a la red). EN: Is WEB_CACHE_ONLY=1 set? (never goes online).
    """
    return os.getenv("WEB_CACHE_ONLY") == "1"


def _clean(text: str) -> str:
    """
    ES: Quita etiquetas HTML (Brave devuelve <strong>) y entidades. EN: Strips HTML tags (Brave returns <strong>) and entities.
    """
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", text or "")).split())


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
        json={"query": query[:MAX_QUERY_CHARS], "max_results": count, "include_domains": list(domains)},
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
    scoped_query = f"{query[:MAX_QUERY_CHARS]} ({' OR '.join(f'site:{d}' for d in domains)})"
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


def _write_cache(path: Path, cache: dict) -> None:
    """
    ES: Escritura atómica (archivo temporal + replace) y con cerrojo: la API atiende peticiones a la vez.
    EN: Atomic write (temp file + replace) under a lock: the API handles concurrent requests.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _cache_key(query: str, n: int, provider_name: str, domains) -> str:
    """
    ES: La clave incluye proveedor, dominios y n: otro proveedor u otro n no deben compartir entrada.
    EN: The key includes provider, domains and n: another provider or n must not share an entry.
    """
    return f"{provider_name}|{','.join(sorted(domains))}|{n}|{' '.join(tokenize(query))}"


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
    Las respuestas vacías no se cachean.
    EN: Searches the web (allowed domains), checking the cache first. `provider` lets tests inject a
    fake provider. Returns dicts with the contract keys (fuente, url, texto...). Empty answers are not cached.
    """
    cache_path = cache_path or CACHE_PATH
    if cache_only is None:
        cache_only = cache_only_enabled()
    provider_name = getattr(provider, "__name__", None) or os.getenv("WEB_PROVIDER", "")
    key = _cache_key(query, n, provider_name, domains)
    entry = _read_cache(cache_path).get(key)
    if entry and (cache_only or time.time() - entry["ts"] < TTL_SECONDS):
        return entry["resultados"][:n]
    if cache_only:
        return []
    raw_results = (provider or _pick_provider())(query, n * 2, domains)
    today = date.today().isoformat()
    results = []
    for r in raw_results:
        text = _clean(r.get("text", ""))
        if text and _domain_allowed(r["url"], domains):
            results.append(
                {
                    "fuente": _clean(r.get("title", "")) or r["url"],
                    "url": r["url"],
                    "texto": text[:MAX_CHARS],
                    "tipo": "web",
                    "origen": "web",
                    "fecha_consulta": today,
                }
            )
    results = results[:n]
    if results:
        with _cache_lock:
            cache = _read_cache(cache_path)
            cache[key] = {"ts": time.time(), "resultados": results}
            _write_cache(cache_path, cache)
    return results
