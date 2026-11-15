import importlib

import pytest
from fastapi.testclient import TestClient

PRODUCCION = "https://pathfinders42-front.vercel.app"
PREVIEW = "https://pathfinders42-front-39vrq9nlg-maxs-projects-f5e577d5.vercel.app"
REGEX = r"https://pathfinders42-front-[a-z0-9-]+-maxs-projects-f5e577d5\.vercel\.app"


@pytest.fixture
def app_cors(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", PRODUCCION)
    monkeypatch.setenv("CORS_ORIGIN_REGEX", REGEX)
    import app.main

    yield TestClient(importlib.reload(app.main).app)
    monkeypatch.delenv("CORS_ORIGIN_REGEX")
    importlib.reload(app.main)


def _permitido(cliente: TestClient, origen: str) -> str | None:
    r = cliente.get("/api/v1/health", headers={"Origin": origen})
    return r.headers.get("access-control-allow-origin")


def test_origen_fijo_y_preview(app_cors):
    assert _permitido(app_cors, PRODUCCION) == PRODUCCION
    assert _permitido(app_cors, PREVIEW) == PREVIEW
    rama = "https://pathfinders42-front-git-dev-maxs-projects-f5e577d5.vercel.app"
    assert _permitido(app_cors, rama) == rama


def test_otros_origenes_no(app_cors):
    assert _permitido(app_cors, "https://otro-proyecto.vercel.app") is None
    assert _permitido(app_cors, PREVIEW + ".evil.com") is None
