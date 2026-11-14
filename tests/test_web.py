"""
ES: Pruebas de la búsqueda web con un proveedor falso (sin red). EN: Web search tests with a fake provider (no network).
"""

import tempfile
from pathlib import Path

from app.explanations.web import search_web

CALLS: list[str] = []


def fake_provider(query, count, domains):
    CALLS.append(query)
    return [
        {"title": "Página NASA (prueba)", "url": "https://www.nasa.gov/prueba", "text": "x" * 900},
        {"title": "Blog cualquiera", "url": "https://blog-falso.example.com/a", "text": "texto"},
        {"title": "Sin texto", "url": "https://www.esa.int/vacio", "text": ""},
    ]


def test_filters_domains_truncates_and_caches():
    cache_path = Path(tempfile.mkdtemp()) / "cache.json"
    results = search_web("cuevas lunares", provider=fake_provider, cache_path=cache_path, cache_only=False)
    assert [r["url"] for r in results] == ["https://www.nasa.gov/prueba"]
    assert len(results[0]["texto"]) == 600 and results[0]["origen"] == "web" and results[0]["fecha_consulta"]
    calls_before = len(CALLS)
    search_web("Cuevas  lunares", provider=fake_provider, cache_path=cache_path, cache_only=False)
    assert len(CALLS) == calls_before  # ES: segunda vez, desde la caché / EN: second time, from cache


def test_cache_only_never_goes_online():
    cache_path = Path(tempfile.mkdtemp()) / "cache.json"
    calls_before = len(CALLS)
    assert search_web("algo nuevo", provider=fake_provider, cache_path=cache_path, cache_only=True) == []
    assert len(CALLS) == calls_before


# ---------------------------------------------------------------------------
# ES: Adaptadores y caché. OJO: usan respuestas SIMULADAS con la forma que creemos que tiene cada API;
# no demuestran que Tavily/Brave respondan así. Hay que probarlos una vez con red y clave reales.
# EN: Adapters and cache. NOTE: they use SIMULATED responses shaped as we believe each API answers;
# they do not prove Tavily/Brave answer that way. Test them once with a real network and key.
# ---------------------------------------------------------------------------
import json  # noqa: E402

import pytest  # noqa: E402

from app.explanations import web  # noqa: E402


class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_tavily_adapter_sends_domains_and_parses_results(monkeypatch):
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        return FakeHttpResponse(
            {"results": [{"title": "T", "url": "https://www.nasa.gov/a", "content": "C"}]}
        )

    monkeypatch.setenv("TAVILY_API_KEY", "clave")
    monkeypatch.setattr(web.httpx, "post", fake_post)
    results = web._tavily("cuevas", 4, ("nasa.gov", "esa.int"))
    assert results == [{"title": "T", "url": "https://www.nasa.gov/a", "text": "C"}]
    assert sent["headers"]["Authorization"] == "Bearer clave"
    assert sent["body"] == {"query": "cuevas", "max_results": 4, "include_domains": ["nasa.gov", "esa.int"]}


def test_brave_adapter_scopes_query_by_site_and_parses_results(monkeypatch):
    sent = {}

    def fake_get(url, params, headers, timeout):
        sent.update(params=params, headers=headers)
        return FakeHttpResponse(
            {"web": {"results": [{"title": "T", "url": "https://www.esa.int/a", "description": "D"}]}}
        )

    monkeypatch.setenv("BRAVE_API_KEY", "clave")
    monkeypatch.setattr(web.httpx, "get", fake_get)
    results = web._brave("cuevas", 4, ("nasa.gov", "esa.int"))
    assert results == [{"title": "T", "url": "https://www.esa.int/a", "text": "D"}]
    assert "site:nasa.gov OR site:esa.int" in sent["params"]["q"]
    assert sent["headers"]["X-Subscription-Token"] == "clave"


def test_adapters_tolerate_empty_responses(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    monkeypatch.setenv("BRAVE_API_KEY", "k")
    monkeypatch.setattr(web.httpx, "post", lambda *a, **k: FakeHttpResponse({}))
    monkeypatch.setattr(web.httpx, "get", lambda *a, **k: FakeHttpResponse({}))
    assert web._tavily("x", 3, ("nasa.gov",)) == [] and web._brave("x", 3, ("nasa.gov",)) == []


def test_provider_configuration(monkeypatch):
    for name in ("WEB_PROVIDER", "TAVILY_API_KEY", "BRAVE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert web.provider_configured() is False
    with pytest.raises(RuntimeError):
        web._pick_provider()
    monkeypatch.setenv("WEB_PROVIDER", "tavily")
    assert web.provider_configured() is False  # provider without key / proveedor sin clave
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    assert web.provider_configured() is True and web._pick_provider() is web._tavily
    monkeypatch.setenv("WEB_PROVIDER", "brave")
    assert web.provider_configured() is False  # brave without its key / brave sin su clave


def test_subdomains_match_but_lookalikes_do_not():
    assert web._domain_allowed("https://science.nasa.gov/x", ("nasa.gov",))
    assert not web._domain_allowed("https://nasa.gov.evil.example/x", ("nasa.gov",))
    assert not web._domain_allowed("https://notnasa.gov/x", ("nasa.gov",))


def test_expired_cache_entry_is_refreshed_but_cache_only_still_serves_it():
    cache_path = Path(tempfile.mkdtemp()) / "cache.json"
    search_web("hielo polar", provider=fake_provider, cache_path=cache_path, cache_only=False)
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    for entry in cache.values():
        entry["ts"] = 0  # very old / muy antigua
    cache_path.write_text(json.dumps(cache), encoding="utf-8")

    calls_before = len(CALLS)
    assert len(search_web("hielo polar", provider=fake_provider, cache_path=cache_path, cache_only=True)) == 1
    assert len(CALLS) == calls_before  # cache_only serves stale data / sirve datos antiguos
    search_web("hielo polar", provider=fake_provider, cache_path=cache_path, cache_only=False)
    assert len(CALLS) == calls_before + 1  # expired: goes online / caducada: sale a la red
