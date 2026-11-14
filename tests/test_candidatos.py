"""Endpoints de M1 con los datos de prueba (tests/fixtures/06_web/m1_v0: 3 candidatos por familia)."""

import pytest

FAMILIAS = {"marte_seco", "volcanico_basaltico"}


def test_listar_todos(cliente):
    r = cliente.get("/api/v1/candidatos")
    assert r.status_code == 200
    cands = r.json()
    assert len(cands) == 6
    assert {c["familia"] for c in cands} == FAMILIAS
    pct = [c["percentil"] for c in cands]
    assert pct == sorted(pct, reverse=True)  # sin familia: mezclados por percentil


def test_listar_por_familia(cliente):
    cands = cliente.get("/api/v1/candidatos", params={"familia": "volcanico_basaltico", "n": 2}).json()
    assert [c["rango"] for c in cands] == [1, 2]
    c = cands[0]
    assert c["id"] == "volcanico_basaltico-1"
    assert 0 <= c["puntuacion"] <= 1 and c["percentil"] >= 99
    assert c["explicacion"] and {"variable", "valor", "contribucion", "sentido"} <= set(c["explicacion"][0])
    assert set(c["variables"]) <= {
        "emis_p_max",
        "frac_emis_p90",
        "frac_volcanica",
        "ndvi_max",
        "frac_desnudo",
    }


def test_solo_nuevos(cliente):
    todos = cliente.get("/api/v1/candidatos").json()
    nuevos = cliente.get("/api/v1/candidatos", params={"solo_nuevos": True}).json()
    assert all(c["nuevo"] for c in nuevos)
    assert len(nuevos) == sum(c["nuevo"] for c in todos)


def test_familia_desconocida(cliente):
    assert cliente.get("/api/v1/candidatos", params={"familia": "nada"}).status_code == 404
    assert cliente.get("/api/v1/candidatos/geojson", params={"familia": "nada"}).status_code == 404
    assert cliente.get("/api/v1/mapas/nada.png").status_code == 404


def test_detalle(cliente):
    r = cliente.get("/api/v1/candidatos/marte_seco-1")
    assert r.status_code == 200
    c = r.json()
    assert c["familia"] == "marte_seco" and c["analogo_cercano"]["dist_km"] >= 0
    assert cliente.get("/api/v1/candidatos/no-existe").status_code == 404


def test_geojson(cliente):
    g = cliente.get("/api/v1/candidatos/geojson", params={"familia": "marte_seco"}).json()
    assert g["type"] == "FeatureCollection" and len(g["features"]) == 3
    f = g["features"][0]
    assert f["geometry"]["type"] == "MultiPolygon"
    assert f["properties"]["familia"] == "marte_seco"


def test_modelo(cliente):
    r = cliente.get("/api/v1/candidatos/modelo")
    assert r.status_code == 200
    m = r.json()
    assert m["version"] == "m1_v0"
    assert {f["id"] for f in m["familias"]} == FAMILIAS
    seco = next(f for f in m["familias"] if f["id"] == "marte_seco")
    assert seco["mapa_url"] == "/api/v1/mapas/marte_seco.png"
    assert seco["n_candidatos"] == 3
    assert seco["validacion"]["celdas"] and seco["importancia"]
    assert seco["monotonia"]["ndvi_max"] == -1
    assert m["leyenda"]["min"] == 80 and m["png_limites"]["norte"] > 85
    assert any(e["id"] == "lofoten_flakstadoy" for e in m["excluidos"])


def test_mapa(cliente):
    r = cliente.get("/api/v1/mapas/marte_seco.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_mapa_no_sincronizado(cliente):
    assert cliente.get("/api/v1/mapas/volcanico_basaltico.png").status_code == 404


@pytest.mark.parametrize(
    "ruta", ["/api/v1/candidatos", "/api/v1/candidatos/modelo", "/api/v1/mapas/marte_seco.png"]
)
def test_sin_datos(cliente_sin_datos, ruta):
    assert cliente_sin_datos.get(ruta).status_code == 503


def test_en_el_openapi(cliente):
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert {"/api/v1/candidatos", "/api/v1/candidatos/modelo", "/api/v1/mapas/{familia}.png"} <= set(rutas)
