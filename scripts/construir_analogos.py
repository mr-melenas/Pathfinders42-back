"""Capa analogos_v0: ficha de cada análogo (sitio de la Luna o Marte ↔ lugar de la Tierra) con pros y contras.

Para cada pareja de la capa `usos` (que une todas las capas) escribe, en español y en inglés:
- pros: capas que pasan su umbral, verificación del lugar (ficha de análogos) y usos de misión para los que es apto;
- contras: capas que no pasan su umbral, diferencia de temperatura en grados y verificación pendiente;
- sin_dato: capas sin medir para esa pareja;
y, una vez por cuerpo, los límites de la Tierra como análogo (gravedad, atmósfera y radiación), con su fuente.

No hay LLM: todo sale de los datos y de la ficha. El LLM solo los explica bajo demanda (POST /preguntar con
`tierra_id`). Entradas: data/06_web (capas `usos` y `sitios`) y scripts/entrada/ficha_analogos.csv.

Uso: python scripts/construir_analogos.py [--web data/06_web]
"""

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VERSION = "analogos_v0"
UMBRAL_BRECHA_C = (
    10  # una diferencia de temperatura media de 10 °C o más es un contra, pase o no la capa clima
)

CAPAS = {
    "topografia": {"es": "Relieve (pendiente y desnivel)", "en": "Relief (slope and local relief)"},
    "geologia": {"es": "Tipo de roca", "en": "Rock type"},
    "clima": {"es": "Temperatura de la superficie (régimen)", "en": "Surface temperature (regime)"},
    "hielo": {"es": "Hielo y permafrost", "en": "Ice and permafrost"},
    "forma_cueva": {"es": "Forma de la cueva (profundidad/diámetro)", "en": "Cave shape (depth/diameter)"},
}
# Datos de cada capa (el sitio y la Tierra), para el pie «capa · fuente»
FUENTES = {
    "topografia": {
        "luna": "LRO LOLA",
        "marte": "HRSC–MOLA",
        "tierra": "Copernicus DEM GLO-30",
    },
    "geologia": {
        "luna": "USGS Unified Geologic Map of the Moon 1:5M",
        "marte": "USGS SIM 3292",
        "tierra": "GLiM",
    },
    "clima": {"luna": "LRO Diviner", "marte": "MACDA v2.0", "tierra": "MODIS MYD11C3"},
    "hielo": {"luna": "LRO Diviner PRP", "marte": "SWIM (NASA/JPL)", "tierra": "Obu et al. (permafrost)"},
    "forma_cueva": {
        "luna": "LROC Lunar Pit Atlas",
        "marte": "MGC³ (USGS)",
        "tierra": "Ficha de análogos y Pyroduct Digital Catalog",
    },
}
USOS_EN = {
    "general": "General",
    "aterrizaje": "Landing and navigation",
    "movilidad": "Rover mobility and robotics",
    "construccion_isru": "Construction and in-situ resources (ISRU)",
    "pruebas_termicas": "Thermal testing of equipment",
    "agua_hielo": "Water, ice and permafrost",
    "cuevas_habitat": "Caves and underground habitat",
}
CUERPOS = {"luna": {"es": "la Luna", "en": "the Moon"}, "marte": {"es": "Marte", "en": "Mars"}}

NSSDC_LUNA = "https://nssdc.gsfc.nasa.gov/planetary/factsheet/moonfact.html"
NSSDC_MARTE = "https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html"
LIMITES = {
    "luna": [
        {
            "id": "gravedad",
            "texto": {
                "es": "Gravedad: 1,62 m/s², una sexta parte de la terrestre. Ningún lugar de la Tierra la reproduce: "
                "el polvo, las ruedas y la excavación se comportan distinto.",
                "en": "Gravity: 1.62 m/s², one sixth of Earth's. No place on Earth reproduces it: dust, wheels and "
                "digging behave differently.",
            },
            "fuente": "NASA NSSDC, Moon Fact Sheet",
            "url": NSSDC_LUNA,
        },
        {
            "id": "atmosfera",
            "texto": {
                "es": "Vacío: la Luna no tiene atmósfera. Sin aire no hay convección que suavice la temperatura, y el "
                "polvo no se erosiona como en la Tierra.",
                "en": "Vacuum: the Moon has no atmosphere. Without air there is no convection to soften temperature, "
                "and dust does not weather as on Earth.",
            },
            "fuente": "NASA NSSDC, Moon Fact Sheet",
            "url": NSSDC_LUNA,
        },
        {
            "id": "radiacion",
            "texto": {
                "es": "Radiación: unos 1369 µSv al día en la superficie (Chang'e 4), más de 200 veces la de la "
                "superficie de la Tierra.",
                "en": "Radiation: about 1369 µSv per day at the surface (Chang'e 4), over 200 times that at Earth's "
                "surface.",
            },
            "fuente": "Zhang et al. (2020), Science Advances 6(39)",
            "url": "https://doi.org/10.1126/sciadv.aaz1334",
        },
    ],
    "marte": [
        {
            "id": "gravedad",
            "texto": {
                "es": "Gravedad: 3,73 m/s², un 38 % de la terrestre. Ningún lugar de la Tierra la reproduce.",
                "en": "Gravity: 3.73 m/s², 38% of Earth's. No place on Earth reproduces it.",
            },
            "fuente": "NASA NSSDC, Mars Fact Sheet",
            "url": NSSDC_MARTE,
        },
        {
            "id": "atmosfera",
            "texto": {
                "es": "Atmósfera: unos 6,36 mb de presión media (menos del 1 % de la terrestre) y un 95 % de CO₂; el "
                "agua líquida no es estable en la superficie.",
                "en": "Atmosphere: about 6.36 mb mean pressure (under 1% of Earth's) and 95% CO₂; liquid water is "
                "not stable at the surface.",
            },
            "fuente": "NASA NSSDC, Mars Fact Sheet",
            "url": NSSDC_MARTE,
        },
        {
            "id": "radiacion",
            "texto": {
                "es": "Radiación: unos 0,67 mSv al día en la superficie (Curiosity, RAD), sin campo magnético global "
                "que la frene.",
                "en": "Radiation: about 0.67 mSv per day at the surface (Curiosity, RAD), with no global magnetic "
                "field to shield it.",
            },
            "fuente": "Hassler et al. (2014), Science 343",
            "url": "https://doi.org/10.1126/science.1244797",
        },
    ],
}

# Ids de las capas que son el mismo lugar que una fila de la ficha de análogos (como en la base de análogos v0)
A_FICHA = {
    "analogo-luna-craters-of-the-moon-idaho": "craters_moon",
    "analogo-luna-kilauea-hawai": "kilauea",
    "analogo-luna-pinacate-sonora": "pinacate",
    "analogo-luna-askja-islandia": "askja",
    "analogo-luna-lanzarote-timanfaya": "lanzarote",
    "analogo-luna-mauna-kea-hawai": "mauna_kea",
    "analogo-luna-meteor-crater-arizona": "meteor_crater",
    "analogo-marte-cuenca-de-qaidam-occidental-lenghu": "qaidam",
    "analogo-marte-isla-axel-heiberg-gypsum-hill-m-a-r-s": "axel_heiberg",
    "analogo-marte-isla-devon-haughton-mars-project": "devon",
    "analogo-marte-desierto-de-atacama-nucleo-hiperarido-ar": "atacama",
    "analogo-marte-valles-secos-de-mcmurdo": "mcmurdo",
    "analogo-marte-lanzarote-esa-pangaea": "lanzarote",
    "analogo-marte-rio-tinto-marte": "rio_tinto",
    "analogo-marte-tso-kar-ladakh-isro-hope": "tso_kar",
    "analogo-marte-university-valley-valles-secos-de-mcmurd": "university_valley",
    "analogo-marte-cuevas-de-hielo-fumarolicas-del-erebus-w": "erebus_cuevas",
    "valentine_cave": "lava_beds",
}


def num(x: float, idioma: str, decimales: int = 2) -> str:
    texto = f"{x:.{decimales}f}"
    return texto.replace(".", ",") if idioma == "es" else texto


def leer(web: Path, rel: str | None) -> dict:
    return json.loads((web / rel).read_text(encoding="utf-8")) if rel else {}


def cargar_ficha(ruta: Path) -> dict[str, dict]:
    with ruta.open(encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def verificacion_de(tid: str, ficha: dict, tierra_capas: dict) -> dict:
    """Verificación del lugar: la ficha de análogos manda; si no está, la capa que lo publica; si es una región
    de los índices de satélite, «hipótesis»."""
    fid = A_FICHA.get(tid, tid)
    if fid in ficha:
        r = ficha[fid]
        url = r.get("url_1") if r.get("url_1", "").startswith("http") else None
        return {
            "ficha_id": fid,
            "verificacion": r.get("verificacion") or "candidato",
            "rasgo": r.get("rasgo_analogo") or None,
            "referencia": r.get("referencia_principal") or None,
            "url": url,
        }
    t = tierra_capas.get(tid, {})
    if t.get("verificacion"):
        return {
            "ficha_id": None,
            "verificacion": t["verificacion"],
            "rasgo": None,
            "referencia": t.get("fuente"),
            "url": None,
        }
    return {"ficha_id": None, "verificacion": "hipótesis", "rasgo": None, "referencia": None, "url": None}


def item_capa(capa: str, d: float, umbral: float, ok: bool, cuerpo: str) -> dict:
    textos = {}
    for idioma in ("es", "en"):
        etiqueta = CAPAS[capa][idioma]
        palabra = ("parecido" if ok else "distinto") if idioma == "es" else ("similar" if ok else "different")
        dist = "distancia" if idioma == "es" else "distance"
        umb = "umbral" if idioma == "es" else "threshold"
        textos[idioma] = f"{etiqueta}: {palabra} ({dist} {num(d, idioma)}; {umb} {num(umbral, idioma, 2)})."
    return {
        "tipo": "capa",
        "capa": capa,
        "distancia": d,
        "umbral": umbral,
        "fuente": f"{FUENTES[capa][cuerpo]} · {FUENTES[capa]['tierra']}",
        "texto": textos,
    }


def item_temperatura(brechas: dict, sitio: str, lugar: str) -> dict | None:
    """Contra por la diferencia en grados (sitio − Tierra), aunque la capa clima compare percentiles y pase."""
    clave = "ts_media" if "ts_media" in brechas else ("t_interior" if "t_interior" in brechas else None)
    if clave is None or abs(brechas[clave]) < UMBRAL_BRECHA_C:
        return None
    b = brechas[clave]
    es_que = "más frío" if b < 0 else "más cálido"
    en_que = "colder" if b < 0 else "warmer"
    es_cual = "de media" if clave == "ts_media" else "en el interior"
    en_cual = "on average" if clave == "ts_media" else "inside"
    texto = {
        "es": f"Temperatura en grados: {sitio} es {num(abs(b), 'es', 0)} °C {es_que} {es_cual} que {lugar}.",
        "en": f"Temperature in degrees: {sitio} is {num(abs(b), 'en', 0)} °C {en_que} {en_cual} than {lugar}.",
    }
    if "ts_min" in brechas and clave == "ts_media":
        bm = brechas["ts_min"]
        texto["es"] += f" La mínima, {num(abs(bm), 'es', 0)} °C {'más fría' if bm < 0 else 'más cálida'}."
        texto["en"] += f" The minimum, {num(abs(bm), 'en', 0)} °C {'colder' if bm < 0 else 'warmer'}."
    return {"tipo": "temperatura", "brechas_C": brechas, "texto": texto}


def lista(nombres: list[str], idioma: str) -> str:
    if not nombres:
        return "—"
    y = " y " if idioma == "es" else " and "
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + y + nombres[-1]


def ficha_pareja(p: dict, sitio: dict, umbrales: dict, usos: dict, ficha: dict, tierra_capas: dict) -> dict:
    cuerpo, nombre_sitio = sitio["cuerpo"], sitio["nombre"]
    ver = verificacion_de(p["tierra_id"], ficha, tierra_capas)
    lugar = p["tierra_nombre"]
    pros, contras = [], []
    for capa in CAPAS:
        if capa in p["distancias"]:
            d = p["distancias"][capa]
            (pros if capa in p["funciona"] else contras).append(
                item_capa(capa, d, umbrales[capa], capa in p["funciona"], cuerpo)
            )
    temp = item_temperatura(p.get("brechas_C") or {}, nombre_sitio, lugar)
    if temp:
        contras.append(temp)

    v = ver["verificacion"]
    if v == "verificada":
        ref = f": {ver['referencia']}" if ver["referencia"] else ""
        pros.append(
            {
                "tipo": "verificacion",
                "texto": {
                    "es": f"Análogo verificado en la literatura{ref}.",
                    "en": f"Analog verified in the literature{ref}.",
                },
                "url": ver["url"],
            }
        )
    elif v == "hipótesis":
        contras.append(
            {
                "tipo": "verificacion",
                "texto": {
                    "es": "Región propuesta por los datos de satélite; ninguna fuente la presenta aún como análogo.",
                    "en": "Region proposed by satellite data; no source presents it as an analog yet.",
                },
            }
        )
    else:
        contras.append(
            {
                "tipo": "verificacion",
                "texto": {
                    "es": f"Análogo {v}: falta una fuente que lo confirme.",
                    "en": f"Analog {'pending' if v == 'pendiente' else 'candidate'}: no source confirms it yet.",
                },
            }
        )

    aptos = [u for u, r in p["usos"].items() if r.get("apta") and u != "general"]
    if aptos:
        pros.append(
            {
                "tipo": "usos",
                "usos": aptos,
                "texto": {
                    "es": "Apto para: " + "; ".join(usos[u] for u in aptos) + ".",
                    "en": "Suitable for: " + "; ".join(USOS_EN.get(u, u) for u in aptos) + ".",
                },
            }
        )

    sin_dato = [c for c in CAPAS if c not in p["distancias"]]
    resumen = {}
    for idioma in ("es", "en"):
        ok = lista([CAPAS[c][idioma].split(" (")[0].lower() for c in p["funciona"]], idioma)
        ko = lista([CAPAS[c][idioma].split(" (")[0].lower() for c in p["falla"]], idioma)
        if idioma == "es":
            partes = [f"funciona en {ok}" if p["funciona"] else "no funciona en ninguna capa medida"]
            partes.append(f"falla en {ko}" if p["falla"] else "no falla en ninguna capa medida")
        else:
            partes = [f"works on {ok}" if p["funciona"] else "works on no measured layer"]
            partes.append(f"fails on {ko}" if p["falla"] else "fails on no measured layer")
        resumen[idioma] = f"{nombre_sitio} ↔ {lugar}: {'; '.join(partes)}."
    general = p["usos"].get("general", {})
    return {
        "tierra_id": p["tierra_id"],
        "tierra_nombre": lugar,
        "tierra_lat": p.get("tierra_lat"),
        "tierra_lon": p.get("tierra_lon"),
        **ver,
        "apta": bool(general.get("apta")),
        "n_capas_ok": len(p["funciona"]),
        "puntuacion": general.get("puntuacion"),
        "resumen": resumen,
        "pros": pros,
        "contras": contras,
        "sin_dato": sin_dato,
        "usos_aptos": aptos,
    }


def construir(web: Path, ficha: dict) -> dict:
    manifest = leer(web, "manifest.json")
    capas = manifest["capas"]
    usos = leer(web, capas["usos"]["archivo"])
    tierra_capas = {}
    for capa in ("cuevas_v2", "anortosita"):
        tierra_capas.update(leer(web, capas[capa]["archivo"]).get("tierra") or {})
    feats = leer(web, capas["sitios"]["archivo"]).get("features", [])
    feats += leer(web, capas["cuevas_v2"]["sitios"]).get("features", [])
    sitios = {f["properties"]["id"]: f["properties"] for f in feats}
    nombres_usos = {u["id"]: u["nombre"] for u in usos["usos"]}

    salida = {}
    for sid, s in usos["sitios"].items():
        if sid not in sitios:
            continue
        sitio = {"nombre": sitios[sid].get("nombre", sid), "cuerpo": sitios[sid].get("cuerpo", "")}
        fichas = [
            ficha_pareja(p, sitio, usos["umbrales"], nombres_usos, ficha, tierra_capas) for p in s["parejas"]
        ]
        # Mismo orden que el uso «general»: aptas, más capas que pasan, mayor puntuación
        fichas.sort(key=lambda f: (not f["apta"], -f["n_capas_ok"], -(f["puntuacion"] or 0), f["tierra_id"]))
        salida[sid] = {**sitio, "analogos": fichas}
    return {
        "version": VERSION,
        "generado": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "umbrales": usos["umbrales"],
        "capas": CAPAS,
        "fuentes_capas": FUENTES,
        "limites_tierra": LIMITES,
        "nota": (
            "Pros y contras calculados de los datos (capa usos_v0) y de la ficha de análogos, sin LLM. Las "
            "distancias van de 0 (igual) a 1; una capa funciona si su distancia es ≤ umbral. Las temperaturas en "
            "grados son un contra aunque la capa clima pase: compara posiciones relativas, no grados."
        ),
        "sitios": salida,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--web", default=str(RAIZ / "data" / "06_web"))
    ap.add_argument("--ficha", default=str(RAIZ / "scripts" / "entrada" / "ficha_analogos.csv"))
    a = ap.parse_args()
    web = Path(a.web)
    capa = construir(web, cargar_ficha(Path(a.ficha)))
    destino = web / VERSION / "analogos.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(capa, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    ruta_m = web / "manifest.json"
    manifest = json.loads(ruta_m.read_text(encoding="utf-8"))
    manifest["capas"]["analogos"] = {
        "version": VERSION,
        "carpeta": VERSION,
        "archivo": f"{VERSION}/analogos.json",
    }
    ruta_m.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fichas = [f for s in capa["sitios"].values() for f in s["analogos"]]
    por_ver: dict[str, int] = {}
    for f in fichas:
        por_ver[f["verificacion"]] = por_ver.get(f["verificacion"], 0) + 1
    print(
        f"{destino}: {len(capa['sitios'])} sitios, {len(fichas)} análogos, "
        f"{destino.stat().st_size / 1024:.0f} kB · verificación {por_ver}"
    )


if __name__ == "__main__":
    main()
