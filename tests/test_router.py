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


# ---------------------------------------------------------------------------
# ES: Endpoint de chat online y límites. EN: Online chat endpoint and limits.
# ---------------------------------------------------------------------------
from app.explanations.retrieval import Bm25Retriever  # noqa: E402


class FakeLLM:
    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), []

    def __call__(self, data, fragments, reminder=""):
        self.calls.append((data, fragments, reminder))
        return self.outputs.pop(0)


@pytest.fixture
def chat(client, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://llm/v1")
    monkeypatch.setattr(router_module, "get_retriever", lambda: Bm25Retriever(TextIndex(TEST_CORPUS)))
    monkeypatch.setattr(router_module, "CHAT_RATE_LIMIT_PER_MIN", 100)
    router_module._chat_requests.clear()
    return client


def _use_llm(monkeypatch, outputs):
    llm = FakeLLM(outputs)
    monkeypatch.setattr(router_module, "get_generator", lambda: llm)
    return llm


def test_ask_answers_with_validated_llm_text(chat, monkeypatch):
    llm = _use_llm(monkeypatch, ["En Malapert la capa clima falla con una brecha de 121.7 °C [1]."])
    body = {"pregunta": "¿Por qué falla el clima en gravedad?", "sitio_id": "artemis-malapert-massif"}
    response = chat.post("/api/v1/preguntar", json=body)
    assert response.status_code == 200
    answer = response.json()
    assert answer["texto_origen"] == "llm" and "121.7" in answer["respuesta"]
    assert answer["fragmentos_usados"][0]["origen"] == "documentacion"
    assert llm.calls[0][0]["pregunta"].startswith("¿Por qué falla")


def test_ask_falls_back_to_template_when_llm_invents_figures(chat, monkeypatch):
    _use_llm(monkeypatch, ["Falla por 999 °C.", "Falla por 888 °C."])
    body = {"pregunta": "¿Por qué falla el clima?", "sitio_id": "artemis-malapert-massif"}
    answer = chat.post("/api/v1/preguntar", json=body).json()
    assert answer["texto_origen"] == "plantilla" and answer["respuesta"].startswith("Malapert Massif (luna)")
    assert answer["fragmentos_usados"] == []


def test_ask_without_site_and_unknown_site(chat, monkeypatch):
    _use_llm(monkeypatch, ["Solo hablo de análogos."])
    assert chat.post("/api/v1/preguntar", json={"pregunta": "hola qué tal"}).status_code == 200
    unknown = chat.post("/api/v1/preguntar", json={"pregunta": "hola", "sitio_id": "no-existe"})
    assert unknown.status_code == 404


def test_ask_requires_llm_and_valid_body(chat, monkeypatch):
    assert chat.post("/api/v1/preguntar", json={"pregunta": "a"}).status_code == 422
    assert chat.post("/api/v1/preguntar", json={"pregunta": "x" * 501}).status_code == 422
    monkeypatch.delenv("LLM_BASE_URL")
    assert chat.post("/api/v1/preguntar", json={"pregunta": "hola"}).status_code == 503


def test_ask_llm_error_is_502_and_web_failure_only_warns(chat, monkeypatch):
    def broken(data, fragments, reminder=""):
        raise httpx.ConnectError("llm caído")

    monkeypatch.setattr(router_module, "get_generator", lambda: broken)
    assert chat.post("/api/v1/preguntar", json={"pregunta": "hola"}).status_code == 502

    _use_llm(monkeypatch, ["Respuesta sin cifras."])
    from app.explanations import writer as writer_module

    def down(query, n=3):
        raise RuntimeError("Búsqueda web no configurada")

    monkeypatch.setattr(writer_module, "search_web", down)
    answer = chat.post("/api/v1/preguntar", json={"pregunta": "hola", "fuente": "web"}).json()
    assert answer["texto_origen"] == "llm" and "aviso" in answer


def test_ask_rate_limit_is_429(chat, monkeypatch):
    _use_llm(monkeypatch, ["a"] * 5)
    monkeypatch.setattr(router_module, "CHAT_RATE_LIMIT_PER_MIN", 2)
    codes = [chat.post("/api/v1/preguntar", json={"pregunta": "hola"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_cache_only_web_search_is_not_rate_limited(client, monkeypatch):
    monkeypatch.setattr(router_module, "WEB_RATE_LIMIT_PER_MIN", 1)
    monkeypatch.setattr(router_module, "search_web", lambda query, n=3: [])
    monkeypatch.setenv("WEB_CACHE_ONLY", "1")
    codes = [
        client.get("/api/v1/buscar", params={"q": "cuevas", "fuente": "web"}).status_code for _ in range(4)
    ]
    assert codes == [200] * 4


def test_client_ip_uses_forwarded_header_only_when_trusted(monkeypatch):
    class Req:
        headers = {"x-forwarded-for": "1.2.3.4, 10.0.0.1"}

        class client:
            host = "10.0.0.1"

    assert router_module._client_ip(Req) == "10.0.0.1"
    monkeypatch.setattr(router_module, "TRUST_PROXY", True)
    assert router_module._client_ip(Req) == "1.2.3.4"
