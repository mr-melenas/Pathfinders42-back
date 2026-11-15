import json
import sys
from pathlib import Path

MALAPERT = "artemis-malapert-massif"
RAIZ = Path(__file__).parent.parent


def test_listar_analogos(cliente):
    r = cliente.get(f"/api/v1/analogos/{MALAPERT}")
    assert r.status_code == 200
    lista = r.json()
    assert lista[0]["tierra_id"] == "lofoten_flakstadoy" and lista[0]["apta"]
    claves = [(not a["apta"], -a["n_capas_ok"]) for a in lista]
    assert claves == sorted(claves)
    assert {"es", "en"} == set(lista[0]["resumen"])


def test_filtros(cliente):
    aptos = cliente.get(f"/api/v1/analogos/{MALAPERT}", params={"solo_aptos": True}).json()
    assert aptos and all(a["apta"] for a in aptos)
    hip = cliente.get(f"/api/v1/analogos/{MALAPERT}", params={"verificacion": "hipótesis"}).json()
    assert hip and all(a["verificacion"] == "hipótesis" for a in hip)
    assert len(cliente.get(f"/api/v1/analogos/{MALAPERT}", params={"n": 1}).json()) == 1


def test_ficha_con_pros_contras_y_limites(cliente):
    f = cliente.get(f"/api/v1/analogos/{MALAPERT}/lofoten_flakstadoy").json()
    assert (
        f["cuerpo"] == "luna" and f["ficha_id"] == "lofoten_flakstadoy" and f["verificacion"] == "verificada"
    )
    capas_pro = {p["capa"] for p in f["pros"] if p["tipo"] == "capa"}
    assert capas_pro == {"topografia", "geologia"}
    for p in f["pros"] + f["contras"]:
        if p["tipo"] == "capa":
            assert (p["distancia"] <= p["umbral"]) == (p in f["pros"])
            assert p["fuente"] and p["texto"]["es"] and p["texto"]["en"]
    assert "clima" in f["sin_dato"]
    assert {lim["id"] for lim in f["limites_tierra"]} == {"gravedad", "atmosfera", "radiacion"}
    assert all(lim["url"].startswith("https://") for lim in f["limites_tierra"])
    assert f["n_pros"] == len(f["pros"]) and f["n_contras"] == len(f["contras"])


def test_region_hipotesis_lleva_contra_de_verificacion(cliente):
    f = cliente.get(f"/api/v1/analogos/{MALAPERT}/luna-11").json()
    assert f["verificacion"] == "hipótesis"
    assert any(c["tipo"] == "verificacion" for c in f["contras"])


def test_errores(cliente):
    assert cliente.get("/api/v1/analogos/no-existe").status_code == 404
    assert cliente.get(f"/api/v1/analogos/{MALAPERT}/no-es-pareja").status_code == 404


def test_script_reproduce_fixture(tmp_path):
    """construir_analogos.py sobre las fixtures da el mismo archivo que está guardado (salvo la fecha)."""
    import shutil

    sys.path.insert(0, str(RAIZ / "scripts"))
    from construir_analogos import cargar_ficha, construir

    web = tmp_path / "06_web"
    shutil.copytree(RAIZ / "tests" / "fixtures" / "06_web", web)
    nuevo = construir(web, cargar_ficha(RAIZ / "scripts" / "entrada" / "ficha_analogos.csv"))
    guardado = json.loads((web / "analogos_v0" / "analogos.json").read_text(encoding="utf-8"))
    nuevo.pop("generado")
    guardado.pop("generado")
    assert nuevo == guardado
