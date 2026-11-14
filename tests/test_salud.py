def test_health(cliente):
    r = cliente.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok", "version_api": "0.3.0", "datos_cargados": True}


def test_health_sin_datos(cliente_sin_datos):
    r = cliente_sin_datos.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["datos_cargados"] is False


def test_meta(cliente):
    r = cliente.get("/api/v1/meta")
    assert r.status_code == 200
    m = r.json()
    assert m["version_manifest"] == "v1.3"
    assert {c["id"] for c in m["cuerpos"]} == {"luna", "marte"}
    capas = {c["id"]: c for c in m["capas"]}
    assert capas["clima"]["disponible"] is True
    assert capas["pendiente"]["disponible"] is False  # su archivo no está en las fixtures
    assert capas["cuevas_v2"]["extras"] == {"sitios": "sitios_cuevas_v0/sitios_cuevas.geojson"}


def test_meta_sin_datos_devuelve_503(cliente_sin_datos):
    assert cliente_sin_datos.get("/api/v1/meta").status_code == 503


def test_openapi_publicado(cliente):
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert {
        "/api/v1/health",
        "/api/v1/meta",
        "/api/v1/capas",
        "/api/v1/capas/{capa}",
        "/api/v1/sitios",
        "/api/v1/sitios/geojson",
        "/api/v1/sitios/{sitio_id}",
        "/api/v1/sitios/{sitio_id}/parejas",
    } <= set(rutas)
