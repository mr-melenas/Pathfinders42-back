"""Comprueba los datos versionados en data/06_web (se salta si no están)."""

import json
from pathlib import Path

import pytest

from app.datos import Datos

DATA = Path(__file__).resolve().parent.parent / "data" / "06_web"
pytestmark = pytest.mark.skipif(not (DATA / "manifest.json").is_file(), reason="sin data/06_web")


def rutas_de_capas(datos: Datos) -> list[tuple[str, str]]:
    return [
        (capa, ruta)
        for capa, info in datos.capas.items()
        for clave, ruta in info.items()
        if clave != "carpeta" and isinstance(ruta, str) and "/" in ruta
    ]


def test_todas_las_capas_tienen_sus_archivos():
    datos = Datos(DATA)
    faltan = [f"{capa}: {ruta}" for capa, ruta in rutas_de_capas(datos) if datos.ruta_segura(ruta) is None]
    assert not faltan, f"Archivos del manifest que no están en data/06_web: {faltan}"


def test_los_json_se_leen():
    datos = Datos(DATA)
    rotos = []
    for capa, ruta in rutas_de_capas(datos):
        if ruta.endswith((".json", ".geojson")):
            try:
                json.loads(datos.ruta_segura(ruta).read_text(encoding="utf-8"))
            except (ValueError, AttributeError) as e:
                rotos.append(f"{capa}: {ruta} ({e})")
    assert not rotos, rotos


def test_version_de_la_sincronizacion():
    version = json.loads((DATA.parent / "VERSION.json").read_text(encoding="utf-8"))
    assert {"sincronizado", "hash", "archivos"} <= set(version)


def test_indice_de_sitios_completo():
    datos = Datos(DATA)
    sitios = datos.sitios.sitios
    assert len(sitios) >= 160  # 97 sitios + 63 sitios-cueva
    sin_capas = [s.id for s in sitios.values() if not s.capas]
    assert not sin_capas, f"Sitios sin datos en ninguna capa: {sin_capas}"


def test_m1_completo():
    datos = Datos(DATA)
    if datos.m1 is None:
        pytest.skip("sin capa m1")
    assert set(datos.m1.familias) == {"marte_seco", "volcanico_basaltico"}
    for familia in datos.m1.familias:
        assert datos.m1.ruta_mapa(familia) is not None, f"falta el mapa de {familia}"
    assert all(c["explicacion"] for c in datos.m1.candidatos.values())


def test_hielo_completo():
    datos = Datos(DATA)
    parejas = datos.hielo.parejas()
    por_cuerpo = {c: sum(p["cuerpo"] == c for p in parejas) for c in ("luna", "marte")}
    assert por_cuerpo == {"luna": 3, "marte": 13}
    lunares = {p["sitio_id"]: p["veredicto"] for p in parejas if p["cuerpo"] == "luna"}
    assert lunares["aterrizaje-im-1-odysseus"] == "debilitada"
    assert all(p["veredicto"] == "sin comprobar" for p in parejas if p["cuerpo"] == "marte")


def test_usos_reales():
    """Con los datos reales, el uso de aterrizaje reproduce las parejas de anortosita_v0 en Artemis."""
    datos = Datos(DATA)
    if not datos.usos.disponible:
        pytest.skip("sin capa usos")
    mejor = datos.usos.parejas("artemis-malapert-massif", "aterrizaje")[0]
    assert mejor["tierra_id"] == "lofoten_flakstadoy" and mejor["apta"]
    jezero = datos.usos.parejas("ez-jezero-isidis-syrtis", "general")
    assert jezero and jezero[0]["apta"]


def test_rag_completo():
    """Corpus y explicaciones generados: una explicación por sitio y fuentes de límites con URL."""
    raiz = DATA.parent / "rag"
    if not (raiz / "explanations.json").is_file():
        pytest.skip("sin data/rag")
    datos = Datos(DATA)
    explicaciones = json.loads((raiz / "explanations.json").read_text(encoding="utf-8"))
    assert set(explicaciones) == set(datos.sitios.sitios)
    fragmentos = [
        json.loads(linea) for linea in (raiz / "corpus.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    tipos = {f["tipo"] for f in fragmentos}
    assert {"limites", "metodo", "ficha"} <= tipos
    assert all(f["url"] for f in fragmentos if f["tipo"] == "limites")
    assert all(e["limites"] for e in explicaciones.values())
