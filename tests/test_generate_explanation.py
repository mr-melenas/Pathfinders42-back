"""
ES: Pruebas del script que genera explicaciones desde la API (la API se sustituye por falsos).
EN: Tests for the script that builds explanations from the API (the API is replaced by fakes).
"""

import json

import httpx
import pytest

from app.explanations.index import TextIndex
from scripts import generate_explanations as script
from tests.sample_data import SAMPLE_RECORD, TEST_CORPUS


class FakeResponse:
    def __init__(self, payload, error=False):
        self.payload, self.error = payload, error

    def raise_for_status(self):
        if self.error:
            raise httpx.HTTPError("boom")

    def json(self):
        return self.payload


def test_generates_one_explanation_per_site(tmp_path, monkeypatch):
    def fake_get(url, timeout=30):
        if url.endswith("/sitios"):
            return FakeResponse([{"id": "artemis-malapert-massif"}])
        if url.endswith("/sitios/artemis-malapert-massif"):
            return FakeResponse(SAMPLE_RECORD)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(script.httpx, "get", fake_get)
    output = tmp_path / "out" / "explanations.json"
    result = script.main("http://api/v1", output, TextIndex(TEST_CORPUS))
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved == result and list(saved) == ["artemis-malapert-massif"]
    assert saved["artemis-malapert-massif"]["donde_falla"] == ["clima"]
    assert len(saved["artemis-malapert-massif"]["limites"]) == 1


def test_api_error_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setattr(script.httpx, "get", lambda url, timeout=30: FakeResponse([], error=True))
    with pytest.raises(httpx.HTTPError):
        script.main("http://api/v1", tmp_path / "x.json", TextIndex([]))
    assert not (tmp_path / "x.json").exists()
