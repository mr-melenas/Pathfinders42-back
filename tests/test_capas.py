def test_listar_capas(cliente):
    r = cliente.get("/api/v1/capas")
    assert r.status_code == 200
    assert [c["id"] for c in r.json()] == [
        "clima",
        "sitios",
        "topografia_sitios",
        "geologia",
        "hielo",
        "cuevas_v2",
        "anortosita",
        "pendiente",
        "trampa",
        "m1",
    ]


def test_capa_json(cliente):
    r = cliente.get("/api/v1/capas/clima")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "artemis-malapert-massif" in r.json()["sitios"]


def test_capa_geojson(cliente):
    r = cliente.get("/api/v1/capas/sitios")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/geo+json")
    assert r.json()["type"] == "FeatureCollection"


def test_capa_desconocida(cliente):
    assert cliente.get("/api/v1/capas/no-existe").status_code == 404


def test_capa_no_sincronizada(cliente):
    assert cliente.get("/api/v1/capas/pendiente").status_code == 404


def test_no_sale_de_la_carpeta_de_datos(cliente):
    assert cliente.get("/api/v1/capas/trampa").status_code == 404
