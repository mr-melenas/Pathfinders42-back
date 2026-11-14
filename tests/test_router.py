"""
ES: Pruebas de los endpoints con TestClient (sin red; la búsqueda web se sustituye por falsos).
EN: Endpoint tests with TestClient (no network; web search is replaced by fakes).
"""

import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.explanations import router as router_module
from app.explanations.generator import explain_record
from app.explanations.index import TextIndex
from tests.sample_data import SAMPLE_RECORD, TEST_CORPUS

WEB_RESULT = {
    "fuente": "Página NASA (prueba)",
    "url": "https://www.nasa.gov/prueba",
    "texto": "dato web",
    "tipo": "web",
    "origen": "web",
    "fecha_consulta": "2026-11-13",
}


@pytest.fixture
def explanations_file(tmp_path):
    path = tmp_path / "explanations.json"
    path.write_text(json.dumps({SAMPLE_RECORD["id"]: explain_record(SAMPLE_RECORD)}), encoding="utf-8")
    return path


@pytest.fixture
def client(explanations_file, monkeypatch):
    monkeypatch.setattr(router_module, "EXPLANATIONS_PATH", explanations_file)
    monkeypatch.setattr(router_module, "_explanations", None)
    monkeypatch.setattr(router_module, "get_index", lambda: TextIndex(TEST_CORPUS))
    monkeypatch.setattr(router_module, "WEB_RATE_LIMIT_PER_MIN", 100)
    router_module._web_requests.clear()
    app = FastAPI()
    app.include_router(router_module.router, prefix="/api/v1")
    return TestClient(app)


def test_get_explanation(client):
    response = client.get("/api/v1/explicaciones/artemis-malapert-massif")
    assert response.status_code == 200
    body = response.json()
    assert body["nombre"] == "Malapert Massif" and body["donde_falla"] == ["clima"]


def test_unknown_site_is_404(client):
    response = client.get("/api/v1/explicaciones/no-existe")
    assert response.status_code == 404 and "no-existe" in response.json()["detail"]


def test_missing_explanations_file_is_503(client, monkeypatch, tmp_path):
    monkeypatch.setattr(router_module, "EXPLANATIONS_PATH", tmp_path / "nada.json")
    monkeypatch.setattr(router_module, "_explanations", None)
    assert client.get("/api/v1/explicaciones/artemis-malapert-massif").status_code == 503


def test_search_docs_by_default_never_touches_web(client, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("web search must not run / la búsqueda web no debe ejecutarse")

    monkeypatch.setattr(router_module, "search_web", boom)
    results = client.get("/api/v1/buscar", params={"q": "gravedad"}).json()
    assert [r["id"] for r in results] == ["t#0"]
    assert results[0]["origen"] == "documentacion" and "puntuacion" in results[0]


def test_search_filters_by_tipo_and_sitio(client):
    by_kind = client.get("/api/v1/buscar", params={"q": "cuevas", "tipo": "paper"}).json()
    assert {r["tipo"] for r in by_kind} == {"paper"}
    by_site = client.get(
        "/api/v1/buscar", params={"q": "cuevas", "sitio_id": "artemis-malapert-massif"}
    ).json()
    assert [r["id"] for r in by_site] == ["t#2"]


def test_search_web_only_and_both(client, monkeypatch):
    monkeypatch.setattr(router_module, "search_web", lambda query, n=3: [WEB_RESULT])
    web_only = client.get("/api/v1/buscar", params={"q": "cuevas", "fuente": "web"}).json()
    assert web_only == [WEB_RESULT]
    both = client.get("/api/v1/buscar", params={"q": "cuevas", "fuente": "ambas"}).json()
    assert [r["origen"] for r in both][-1] == "web" and "documentacion" in {r["origen"] for r in both}


def test_web_not_configured_is_503(client, monkeypatch):
    def not_configured(query, n=3):
        raise RuntimeError("Búsqueda web no configurada")

    monkeypatch.setattr(router_module, "search_web", not_configured)
    response = client.get("/api/v1/buscar", params={"q": "cuevas", "fuente": "web"})
    assert response.status_code == 503 and "no configurada" in response.json()["detail"]


def test_web_provider_error_is_502(client, monkeypatch):
    def provider_down(query, n=3):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(router_module, "search_web", provider_down)
    assert client.get("/api/v1/buscar", params={"q": "cuevas", "fuente": "web"}).status_code == 502


def test_web_rate_limit_is_429(client, monkeypatch):
    monkeypatch.setattr(router_module, "WEB_RATE_LIMIT_PER_MIN", 2)
    monkeypatch.setattr(router_module, "search_web", lambda query, n=3: [])
    codes = [
        client.get("/api/v1/buscar", params={"q": "cuevas", "fuente": "web"}).status_code for _ in range(3)
    ]
    assert codes == [200, 200, 429]
    # ES: las búsquedas solo de documentación no cuentan para el límite / EN: docs-only searches don't count
    assert client.get("/api/v1/buscar", params={"q": "cuevas"}).status_code == 200


def test_invalid_parameters_are_422(client):
    assert client.get("/api/v1/buscar", params={"q": "a"}).status_code == 422
    assert client.get("/api/v1/buscar", params={"q": "cuevas", "fuente": "otra"}).status_code == 422
    assert client.get("/api/v1/buscar", params={"q": "cuevas", "n": 99}).status_code == 422


def test_sources_are_unique_and_sorted(client):
    sources = client.get("/api/v1/fuentes").json()
    assert [s["fuente"] for s in sources] == ["Fuente de prueba", "Otra fuente"]
    assert sources[1]["url"] == "https://example.org/b"
