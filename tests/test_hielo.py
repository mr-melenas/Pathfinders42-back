MALAPERT = "artemis-malapert-massif"
IM1 = "aterrizaje-im-1-odysseus"
DEUTERONILUS = "ez-deuteronilus-mensae-2"


def test_resumen(cliente):
    r = cliente.get("/api/v1/hielo")
    assert r.status_code == 200
    d = r.json()
    assert d["versiones"] == {"hielo": "hielo_v0", "hielo_lro": "hielo_v1.1"}
    assert d["n_parejas"] == {"luna": 1, "marte": 1}
    assert d["veredictos"] == {"debilitada": 1, "sin comprobar": 1}
    assert d["niveles_lro"] == {"solo hidrógeno": 1, "solo frío": 1}
    assert d["umbrales"]["hielo_v1.1"]["lend_z_polo"] == 2.0
    assert d["avisos"] and {f["instrumento"] for f in d["fuentes"]} == {"Diviner PRP", "Mini-RF", "LEND"}


def test_sitios_filtros(cliente):
    todos = cliente.get("/api/v1/hielo/sitios").json()
    assert len(todos) == 4
    luna = cliente.get("/api/v1/hielo/sitios", params={"cuerpo": "luna"}).json()
    assert {s["id"] for s in luna} == {MALAPERT, IM1}
    con = cliente.get("/api/v1/hielo/sitios", params={"solo_analogos": True}).json()
    assert {s["id"] for s in con} == {IM1, DEUTERONILUS}
    assert cliente.get("/api/v1/hielo/sitios", params={"cuerpo": "venus"}).status_code == 422


def test_tiene_analogo_sin_datos_es_none(cliente):
    s = next(x for x in cliente.get("/api/v1/hielo/sitios").json() if x["id"] == "aterrizaje-mars-3")
    assert s["tiene_analogo"] is None and s["nivel_lro"] is None


def test_ficha_con_lro(cliente):
    r = cliente.get(f"/api/v1/hielo/sitios/{IM1}")
    assert r.status_code == 200
    d = r.json()
    assert d["mejor_region"].startswith("Isla Axel Heiberg")
    assert d["regiones"][0]["region_id"] == "analogo-marte-isla-axel-heiberg-gypsum-hill-m-a-r-s"
    lro = d["lro"]
    assert lro["nivel"] == "solo frío" and lro["senal_diviner"] and not lro["senal_lend"]
    assert lro["lend_radios_con_senal"] == 0 and lro["rugosidad_radar"] in {"baja", "media", "alta"}


def test_ficha_marte_sin_lro(cliente):
    d = cliente.get(f"/api/v1/hielo/sitios/{DEUTERONILUS}").json()
    assert d["lro"] is None and d["h2o_grs_pct"] is not None


def test_sitio_desconocido(cliente):
    assert cliente.get("/api/v1/hielo/sitios/no-existe").status_code == 404


def test_parejas_y_veredictos(cliente):
    parejas = cliente.get("/api/v1/hielo/parejas").json()
    assert [p["sitio_id"] for p in parejas] == [IM1, DEUTERONILUS]  # luna antes que marte
    im1, deut = parejas
    assert im1["veredicto"] == "debilitada" and "temperatura" in im1["motivo"]
    assert im1["region"]["region"].startswith("Isla Axel Heiberg")
    assert deut["veredicto"] == "sin comprobar" and "SWIM" in deut["motivo"]
    assert deut["nivel_lro"] is None


def test_parejas_filtros(cliente):
    r = cliente.get("/api/v1/hielo/parejas", params={"cuerpo": "marte"}).json()
    assert [p["sitio_id"] for p in r] == [DEUTERONILUS]
    r = cliente.get("/api/v1/hielo/parejas", params={"veredicto": "se mantiene"}).json()
    assert r == []
    assert cliente.get("/api/v1/hielo/parejas", params={"veredicto": "quizá"}).status_code == 422


def test_sin_capa_lro(cliente, monkeypatch):
    from app.dependencias import obtener_datos

    datos = obtener_datos()
    capas = {k: v for k, v in datos.capas.items() if k != "hielo_lro"}
    monkeypatch.setattr(datos, "manifest", {**datos.manifest, "capas": capas})
    datos.__dict__.pop("hielo", None)
    try:
        d = cliente.get(f"/api/v1/hielo/sitios/{IM1}").json()
        assert d["lro"] is None
        pareja = cliente.get("/api/v1/hielo/parejas", params={"cuerpo": "luna"}).json()[0]
        assert pareja["veredicto"] == "sin comprobar"
    finally:
        datos.__dict__.pop("hielo", None)


def test_openapi_documenta_hielo(cliente):
    esquema = cliente.get("/openapi.json").json()
    assert {
        "/api/v1/hielo",
        "/api/v1/hielo/sitios",
        "/api/v1/hielo/sitios/{sitio_id}",
        "/api/v1/hielo/parejas",
    } <= set(esquema["paths"])
    veredicto = esquema["components"]["schemas"]["ParejaHielo"]["properties"]["veredicto"]
    assert "$ref" in veredicto or "enum" in veredicto
