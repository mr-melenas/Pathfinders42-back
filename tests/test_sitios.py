MALAPERT = "artemis-malapert-massif"
CUEVA = "cueva-luna-marius-hills-pit"


def test_listar_sitios(cliente):
    r = cliente.get("/api/v1/sitios")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert ids == {MALAPERT, "aterrizaje-mars-3", CUEVA}


def test_filtros(cliente):
    luna = cliente.get("/api/v1/sitios", params={"cuerpo": "luna"}).json()
    assert {s["id"] for s in luna} == {MALAPERT, CUEVA}
    cuevas = cliente.get("/api/v1/sitios", params={"capa": "cuevas"}).json()
    assert [s["id"] for s in cuevas] == [CUEVA]
    assert cliente.get("/api/v1/sitios", params={"capa": "nada"}).status_code == 422


def test_resumen_de_sitio(cliente):
    s = next(x for x in cliente.get("/api/v1/sitios").json() if x["id"] == MALAPERT)
    assert s["cuerpo"] == "luna" and s["lat"] < -80
    assert set(s["capas"]) == {"topografia", "clima", "geologia", "hielo", "anortosita"}
    assert s["parecidos"]["anortosita"] is True  # Malapert ↔ Lofoten es análogo completo


def test_detalle(cliente):
    r = cliente.get(f"/api/v1/sitios/{MALAPERT}")
    assert r.status_code == 200
    d = r.json()
    assert d["geometria"]["type"] == "Polygon"
    capas = {c["capa"]: c for c in d["resumen"]}
    assert capas["anortosita"]["mejor"]["id"] == "lofoten_flakstadoy"
    assert "top3" not in d["datos_capas"]["anortosita"]  # las listas de parejas van en /parejas
    assert d["datos_capas"]["geologia"]["clase_dominante"] == "anortosita"


def test_detalle_cueva(cliente):
    d = cliente.get(f"/api/v1/sitios/{CUEVA}").json()
    assert d["tipo"] == "cueva_luna"
    assert d["propiedades"]["tipo_cueva"] == "tragaluz_tubo_lava"
    assert set(d["capas"]) == {"topografia", "cuevas"}


def test_sitio_desconocido(cliente):
    assert cliente.get("/api/v1/sitios/no-existe").status_code == 404
    assert cliente.get("/api/v1/sitios/no-existe/parejas").status_code == 404


def test_parejas_ordenadas(cliente):
    r = cliente.get(f"/api/v1/sitios/{MALAPERT}/parejas", params={"capa": "geologia"})
    assert r.status_code == 200
    parejas = r.json()
    # primero las marcadas como análogo, luego por distancia
    claves = [(p["parecido"] is not True, p["distancia"]) for p in parejas]
    assert claves == sorted(claves)
    assert all({"id", "nombre", "distancia", "parecido", "detalles"} <= set(p) for p in r.json())


def test_parejas_n(cliente):
    r = cliente.get(f"/api/v1/sitios/{MALAPERT}/parejas", params={"capa": "topografia", "n": 2})
    assert len(r.json()) == 2


def test_parejas_capa_sin_datos(cliente):
    r = cliente.get(f"/api/v1/sitios/{CUEVA}/parejas", params={"capa": "clima"})
    assert r.status_code == 404
    assert "topografia" in r.json()["detail"]


def test_geojson(cliente):
    g = cliente.get("/api/v1/sitios/geojson").json()
    assert g["type"] == "FeatureCollection"
    assert len(g["features"]) == 3
    assert all(f["geometry"] for f in g["features"])
