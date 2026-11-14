from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures" / "06_web"


@pytest.fixture
def cliente(monkeypatch):
    from app.datos import cargar

    monkeypatch.setenv("DATA_DIR", str(FIXTURES))
    cargar.cache_clear()
    from app.main import app

    yield TestClient(app)
    cargar.cache_clear()


@pytest.fixture
def cliente_sin_datos(monkeypatch, tmp_path):
    from app.datos import cargar

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cargar.cache_clear()
    from app.main import app

    yield TestClient(app)
    cargar.cache_clear()
