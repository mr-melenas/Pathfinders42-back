import json
import shutil
from pathlib import Path

import pytest

from scripts.sync_data import main, sincronizar

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


def _origen_sin_usos(tmp_path: Path) -> Path:
    """Copia de las fixtures como vendrían de Drive: sin la capa usos (se genera en el repo)."""
    origen = tmp_path / "origen"
    shutil.copytree(FIXTURES, origen)
    shutil.rmtree(origen / "usos_v0")
    manifest = json.loads((origen / "manifest.json").read_text(encoding="utf-8"))
    del manifest["capas"]["usos"]
    (origen / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return origen


def test_main_reconstruye_usos(tmp_path, monkeypatch):
    origen, destino = _origen_sin_usos(tmp_path), tmp_path / "data" / "06_web"
    monkeypatch.setattr("sys.argv", ["sync_data.py", "--origen", str(origen), "--destino", str(destino)])
    main()
    assert (destino / "usos_v0" / "usos.json").is_file()
    manifest = json.loads((destino / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["capas"]["usos"]["archivo"] == "usos_v0/usos.json"


def test_main_sin_usos(tmp_path, monkeypatch):
    origen, destino = _origen_sin_usos(tmp_path), tmp_path / "data" / "06_web"
    argv = ["sync_data.py", "--origen", str(origen), "--destino", str(destino), "--sin-usos"]
    monkeypatch.setattr("sys.argv", argv)
    main()
    assert not (destino / "usos_v0").exists()
