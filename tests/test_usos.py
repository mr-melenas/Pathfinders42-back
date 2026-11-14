import json
import sys
from pathlib import Path

MALAPERT = "artemis-malapert-massif"
MARS3 = "aterrizaje-mars-3"
CUEVA = "cueva-luna-marius-hills-pit"
RAIZ = Path(__file__).parent.parent


def test_listar_usos(cliente):
    r = cliente.get("/api/v1/usos")
    assert r.status_code == 200
    d = r.json()
    ids = [u["id"] for u in d["usos"]]
    assert ids[0] == "general" and {"aterrizaje", "agua_hielo", "cuevas_habitat"} <= set(ids)
    assert d["umbrales"]["topografia"] == 0.2 and d["umbrales"]["geologia"] == 0.4
    cuevas = next(u for u in d["usos"] if u["id"] == "cuevas_habitat")
    assert cuevas["solo_sitios"] == "cuevas" and cuevas["n_sitios"] == 1


def test_parejas_por_uso_ordenadas(cliente):
    r = cliente.get(f"/api/v1/usos/construccion_isru/sitios/{MALAPERT}")
    assert r.status_code == 200
    parejas = r.json()
    assert parejas
    claves = [(not p["apta"], -p["puntuacion"]) for p in parejas]
    assert claves == sorted(claves)
    assert all("geologia" in p["distancias"] for p in parejas)  # capa obligatoria del uso


def test_funciona_y_falla_coherentes(cliente):
    usos = cliente.get("/api/v1/usos").json()["umbrales"]
    for p in cliente.get(f"/api/v1/usos/general/sitios/{MALAPERT}", params={"n": 50}).json():
        for capa in p["funciona"]:
            assert p["distancias"][capa] <= usos[capa]
        for capa in p["falla"]:
            assert p["distancias"][capa] > usos[capa]
        assert not set(p["sin_dato"]) & set(p["distancias"])


def test_general_ordena_por_capas_ok(cliente):
    parejas = cliente.get(f"/api/v1/usos/general/sitios/{MALAPERT}", params={"n": 50}).json()
    claves = [(not p["apta"], -p["n_capas_ok"], -p["puntuacion"]) for p in parejas]
    assert claves == sorted(claves)
    assert all(p["n_capas_ok"] >= 2 for p in parejas if p["apta"])


def test_solo_aptas_y_n(cliente):
    todas = cliente.get(f"/api/v1/usos/aterrizaje/sitios/{MALAPERT}", params={"n": 50}).json()
    aptas = cliente.get(
        f"/api/v1/usos/aterrizaje/sitios/{MALAPERT}", params={"n": 50, "solo_aptas": True}
    ).json()
    assert all(p["apta"] for p in aptas) and len(aptas) <= len(todas)
    assert len(cliente.get(f"/api/v1/usos/aterrizaje/sitios/{MALAPERT}", params={"n": 1}).json()) == 1


def test_usos_limitados(cliente):
    # Marius Hills es una cueva: entra en cuevas_habitat; Mars 3 no
    assert cliente.get(f"/api/v1/usos/cuevas_habitat/sitios/{CUEVA}").json()
    assert cliente.get(f"/api/v1/usos/cuevas_habitat/sitios/{MARS3}").json() == []


def test_ranking(cliente):
    r = cliente.get("/api/v1/usos/aterrizaje/ranking", params={"cuerpo": "luna"})
    assert r.status_code == 200
    filas = r.json()
    assert {f["sitio_id"] for f in filas} <= {MALAPERT, CUEVA}
    assert all(f["cuerpo"] == "luna" and f["mejor"] for f in filas)


def test_errores(cliente):
    assert cliente.get("/api/v1/usos/nada/sitios/x").status_code == 404
    assert cliente.get("/api/v1/usos/nada/ranking").status_code == 404
    assert cliente.get("/api/v1/usos/general/sitios/no-existe").status_code == 404


def test_sin_capa(cliente_sin_datos):
    assert cliente_sin_datos.get("/api/v1/usos").status_code in (404, 503)


def test_script_reproduce_fixture(tmp_path):
    """construir_usos.py sobre las fixtures da el mismo archivo que está guardado (salvo la fecha)."""
    import shutil

    sys.path.insert(0, str(RAIZ / "scripts"))
    from construir_usos import cargar_glim, construir

    web = tmp_path / "06_web"
    shutil.copytree(RAIZ / "tests" / "fixtures" / "06_web", web)
    config = json.loads((RAIZ / "scripts" / "usos.json").read_text(encoding="utf-8"))
    nuevo = construir(web, config, cargar_glim(RAIZ / "scripts" / "entrada" / "geologia_tierra_glim.csv"))
    guardado = json.loads((web / "usos_v0" / "usos.json").read_text(encoding="utf-8"))
    nuevo.pop("generado")
    guardado.pop("generado")
    assert nuevo == guardado
