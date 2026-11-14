import json
import shutil
from pathlib import Path

import pytest

from scripts.sync_data import sincronizar

FIXTURES = Path(__file__).parent / "fixtures" / "06_web"


def test_sincronizar(tmp_path):
    destino = tmp_path / "data" / "06_web"
    version = sincronizar(FIXTURES, destino)
    assert (destino / "manifest.json").is_file()
    assert (destino / "clima_v1" / "clima.json").is_file()
    guardado = json.loads((tmp_path / "data" / "VERSION.json").read_text())
    assert guardado == version
    assert version["archivos"] == len([p for p in FIXTURES.rglob("*") if p.is_file()])
    assert version["manifest_version"] == "v1.3"


def test_hash_estable(tmp_path):
    a = sincronizar(FIXTURES, tmp_path / "a" / "06_web")
    b = sincronizar(FIXTURES, tmp_path / "b" / "06_web")
    assert a["hash"] == b["hash"]


def test_origen_sin_manifest(tmp_path):
    origen = tmp_path / "vacio"
    origen.mkdir()
    with pytest.raises(SystemExit):
        sincronizar(origen, tmp_path / "data" / "06_web")


def test_resincronizar_reemplaza(tmp_path):
    origen = tmp_path / "origen"
    shutil.copytree(FIXTURES, origen)
    destino = tmp_path / "data" / "06_web"
    sincronizar(origen, destino)
    (origen / "clima_v1" / "clima.json").unlink()
    sincronizar(origen, destino)
    assert not (destino / "clima_v1" / "clima.json").exists()
