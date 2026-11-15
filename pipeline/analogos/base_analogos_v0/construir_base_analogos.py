"""Base de análogos v0: todos los sitios análogos de la Tierra con su nivel de confianza
y las parejas comprobadas Tierra ↔ Luna/Marte.

Entradas
- data/06_web del backend (Pathfinders42-back): capas ya calculadas en Colab.
- entrada/ficha_fichas.csv: copia de la Google Sheet «ficha_analogos» (pestaña Fichas, 14 nov 2026).
- entrada/geologia_tierra_glim.csv: copia de 04_resultados/geologia_v0 (fracciones GLiM por región).

Salidas (carpeta salida/)
- analogos_tierra.csv        base 1: una fila por sitio o región de la Tierra
- parejas_luna_marte.csv     base 2: todas las parejas evaluadas (unión de los top de cada capa)
- parejas_comprobadas.csv    base 2 filtrada: nivel Alta o Media
- sitios_luna_marte.csv      resumen por sitio de la Luna o Marte (su mejor pareja)
- huecos.csv                 qué falta por mejorar
- base_analogos.geojson      puntos de la Tierra y de las parejas para verlos en un mapa

Uso: python construir_base_analogos.py --web <ruta a data/06_web> --entrada entrada --salida salida
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

# Umbrales de cada capa (los mismos que en los cierres)
U_TOPO, U_GEO, U_HIELO, U_CLIMA, U_FORMA = 0.2, 0.4, 0.25, 0.2, 0.3
# La capa de hielo solo cuenta si el sitio tiene hielo (≥ 20 % del sitio, como en hielo_v0:
# 11 sitios de la Luna y 24 de Marte). Si no, «sin hielo frente a sin permafrost» no prueba nada.
F_HIELO_MIN = 0.2

GLIM_COLS = ["su", "ss", "sm", "py", "sc", "ev", "mt", "pa", "pi", "pb", "va", "vi", "vb", "ig"]

# Ids de las capas que son el mismo lugar que una fila de la ficha
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
# Nombre en luna_v0.3/analogos.geojson → id de la ficha
LUNA_NOMBRE_A_FICHA = {
    "Craters of the Moon, Idaho": "craters_moon", "Kīlauea, Hawái": "kilauea",
    "Pinacate, Sonora": "pinacate", "Askja, Islandia": "askja",
    "Lanzarote – Timanfaya": "lanzarote", "Mauna Kea, Hawái": "mauna_kea",
    "Meteor Crater, Arizona": "meteor_crater",
}
PUNTOS_EVIDENCIA = {"verificada": 3, "pendiente": 2, "candidato": 1, "hipótesis": 0}
PUNTOS_NIVEL = {"Alta": 3, "Media": 2, "Baja": 1, "Sin respaldo": 0}
ORDEN_NIVEL = ["Alta", "Media", "Baja", "Muy baja (hipótesis)", "Sin datos"]


def km(lat1, lon1, lat2, lon2):
    if any(pd.isna(x) for x in (lat1, lon1, lat2, lon2)):
        return np.nan
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def cuerpo_de_perfil(perfil: str) -> str:
    p = (perfil or "").lower()
    luna, marte = "luna" in p, "marte" in p
    if luna and marte:
        return "luna y marte"
    if luna:
        return "luna"
    if marte:
        return "marte"
    return "otro" if p else ""


def cargar(web: Path, entrada: Path):
    j = lambda p: json.load(open(web / p, encoding="utf-8"))  # noqa: E731
    return {
        "ficha": pd.read_csv(entrada / "ficha_fichas.csv", dtype={"lat": float, "lon": float}).fillna({c: "" for c in ["coord_nota", "perfil", "rasgo_analogo", "tipo_geologico", "referencia_principal", "url_1"]}),
        "glim": pd.read_csv(entrada / "geologia_tierra_glim.csv").set_index("region_id"),
        "sitios": j("sitios_v0/sitios.geojson"),
        "sitios_cuevas": j("sitios_cuevas_v0/sitios_cuevas.geojson"),
        "reg_marte": j("v1.3/regiones.geojson"),
        "ana_marte": j("v1.3/analogos.geojson"),
        "reg_luna": j("luna_v0.3/regiones.geojson"),
        "ana_luna": j("luna_v0.3/analogos.geojson"),
        "m1": j("m1_v0/candidatos.json"),
        "topo": j("topografia_sitios_v2/topografia_sitios.json"),
        "geo": j("geologia_v0/geologia_sitios.json"),
        "hielo": j("hielo_v0/hielo.json"),
        "clima": j("clima_v1/clima.json"),
        "cuevas": j("cuevas_v2/cuevas.json"),
        "anort": j("anortosita_v0/anortosita.json"),
    }


# ---------------------------------------------------------------- sitios de la Luna y Marte
def sitios_luna_marte(d) -> pd.DataFrame:
    filas = []
    for f in d["sitios"]["features"]:
        p = f["properties"]
        if f["geometry"]["type"] == "Point":
            lon, lat = f["geometry"]["coordinates"][:2]
        else:  # regiones Artemis: centro que da la fuente
            lat, lon = p["lat_centro"], p["lon_centro"]
        filas.append(dict(sitio_id=p["id"], sitio=p["nombre"], cuerpo=p["cuerpo"], tipo_sitio=p["tipo"],
                          sitio_lat=round(lat, 4), sitio_lon=round(lon, 4)))
    for f in d["sitios_cuevas"]["features"]:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        filas.append(dict(sitio_id=p["id"], sitio=p["nombre"], cuerpo=p["cuerpo"],
                          tipo_sitio=f"cueva ({p['tipo_cueva']})", sitio_lat=lat, sitio_lon=lon))
    s = pd.DataFrame(filas)
    hielo = {k: v.get("f_hielo") for k, v in d["hielo"]["sitios"].items()}
    s["f_hielo_sitio"] = s["sitio_id"].map(hielo)
    return s


# ---------------------------------------------------------------- base 1 (sin el respaldo de parejas)
def entidades_tierra(d) -> tuple[pd.DataFrame, dict]:
    filas = []
    fusionadas = []

    # percentiles de los índices y de M1 para los sitios conocidos
    pct_marte = {f["properties"]["id"]: f["properties"].get("sat_percentil") for f in d["ana_marte"]["features"]}
    pct_luna = {}
    for f in d["ana_luna"]["features"]:
        fid = LUNA_NOMBRE_A_FICHA.get(f["properties"]["nombre"])
        if fid:
            pct_luna[fid] = f["properties"].get("percentil")
    pct_m1 = {}
    for fam in d["m1"]["familias"].values():
        for c in fam["validacion"]["celdas"]:
            for a in c["analogos"]:
                pct_m1[a] = c["percentil_m1"]

    # A. ficha
    for _, r in d["ficha"].iterrows():
        if r["id"] == "islandia":
            fusionadas.append(dict(id="islandia", nota="fila genérica; la cubren askja, surtshellir, lofthellir y krafla_fisuras"))
            continue
        pi = [x for x in (pct_marte.get(r["id"]), pct_luna.get(r["id"])) if x is not None and not pd.isna(x)]
        filas.append(dict(
            id=r["id"], nombre=r["nombre"], pais_region=r["pais"], lat=r["lat"], lon=r["lon"],
            coord_nota=r["coord_nota"], cuerpo_objetivo=cuerpo_de_perfil(r["perfil"]), perfil=r["perfil"],
            tipo_entidad="sitio de la ficha", origen="ficha_analogos (Google Sheet)",
            verificacion=r["verificacion"], rasgo_analogo=r["rasgo_analogo"], tipo_geologico=r["tipo_geologico"],
            referencia=r["referencia_principal"], url=r["url_1"],
            percentil_indice=max(pi) if pi else np.nan, percentil_m1=pct_m1.get(r["id"], np.nan),
        ))

    # B. cuevas de la Tierra que no están en la ficha
    ids_ficha = set(d["ficha"]["id"])
    for k, v in d["cuevas"]["tierra"].items():
        if k in ids_ficha or A_FICHA.get(k) in ids_ficha:
            continue
        filas.append(dict(
            id=k, nombre=v["nombre"], pais_region="", lat=v["lat"], lon=v["lon"], coord_nota="según la capa cuevas_v2",
            cuerpo_objetivo="luna y marte", perfil=f"cueva ({v['tipo_cueva']})", tipo_entidad="cueva de la capa cuevas_v2",
            origen="cuevas_v2", verificacion=v["verificacion"], rasgo_analogo="tubo de lava", tipo_geologico="",
            referencia=v.get("fuente") or "", url="", percentil_indice=np.nan, percentil_m1=np.nan,
        ))

    # C. campos volcánicos de la prueba ciega (geología conocida; sin fuente que los llame análogos)
    ciega = {c["nombre"]: c for c in d["m1"]["familias"]["volcanico_basaltico"]["validacion"]["prueba_ciega"]}
    for f in d["ana_luna"]["features"]:
        p = f["properties"]
        if p["tipo"] != "volcanico_prueba":
            continue
        lon, lat = f["geometry"]["coordinates"]
        slug = "campo-" + p["nombre"].split(",")[0].lower().replace(" – ", "-").replace(" ", "-").replace("ú", "u")
        filas.append(dict(
            id=slug, nombre=p["nombre"], pais_region=p["nombre"].split(", ")[-1], lat=lat, lon=lon,
            coord_nota="según luna_v0.3", cuerpo_objetivo="luna", perfil="Luna (basalto)",
            tipo_entidad="campo volcánico de prueba", origen="luna_v0.3 y prueba ciega de M1",
            verificacion="hipótesis", rasgo_analogo="campo de basalto desnudo (prueba ciega de los índices)",
            tipo_geologico="campo volcánico basáltico", referencia="", url="",
            percentil_indice=p.get("percentil"), percentil_m1=ciega.get(p["nombre"], {}).get("percentil_m1", np.nan),
        ))

    # D. regiones del índice de Marte (v1.3) y de la Luna (luna_v0.3)
    centros = {k: (v["lat_c"], v["lon_c"]) for k, v in d["hielo"]["tierra"].items()}
    for f in d["reg_marte"]["features"] + d["reg_luna"]["features"]:
        p = f["properties"]
        lat, lon = centros.get(p["id"], (p["mejor_celda"][1], p["mejor_celda"][0]))
        es_luna = p["perfil"] == "luna"
        filas.append(dict(
            id=p["id"], nombre=f"{p['nombre']} — {p['region']}", pais_region=p["region"], lat=lat, lon=lon,
            coord_nota="centro de la región (celdas del índice)", cuerpo_objetivo="luna" if es_luna else "marte",
            perfil=p["nombre"], tipo_entidad="región del índice",
            origen="luna_v0.3" if es_luna else "v1.3 (índice de Marte)", verificacion="hipótesis",
            rasgo_analogo=p.get("descripcion", ""),
            tipo_geologico=p.get("litologia_glim", "") if es_luna else "",
            referencia="", url="",
            percentil_indice=p.get("percentil_max", p.get("percentil_medio")), percentil_m1=np.nan,
            analogo_conocido_indice=p.get("analogo_conocido"), area_km2=p.get("area_km2"),
        ))

    # E. candidatos de M1
    for fam_id, fam in d["m1"]["familias"].items():
        for c in fam["candidatos"]:
            filas.append(dict(
                id=c["id"], nombre=c["nombre"], pais_region=c.get("pais_iso", ""), lat=c["lat"], lon=c["lon"],
                coord_nota="mejor celda de ~50 km de la región candidata", cuerpo_objetivo="marte" if fam_id == "marte_seco" else "luna",
                perfil=fam["nombre"], tipo_entidad="candidato de M1", origen="m1_v0 (LightGBM, aprendizaje PU)",
                verificacion="hipótesis", rasgo_analogo=fam.get("descripcion", ""), tipo_geologico="",
                referencia="", url="", percentil_indice=np.nan, percentil_m1=c["percentil"],
                m1_nuevo="sí" if c["nuevo"] else "no", area_km2=c.get("area_km2"),
            ))
    t = pd.DataFrame(filas)
    return t, {"fusionadas": fusionadas}


# ---------------------------------------------------------------- base 2: parejas
def site_mix(site_geo, eq):
    m = {c: 0.0 for c in GLIM_COLS + ["wb", "nd"]}
    for cl, pesos in eq.items():
        f = site_geo.get("f_" + cl) or 0
        for k, w in pesos.items():
            m[k] += f * w
    return m


def dist_geo(site_geo, region_id, d):
    """1 − fracción de roca compartida (reproduce geologia_v0: sin agua ni sin dato, renormalizado)."""
    if site_geo is None or region_id not in d["glim"].index:
        return np.nan
    r = d["glim"].loc[region_id]
    tot = sum(r[c] for c in GLIM_COLS)
    if tot <= 0:
        return np.nan
    m = site_mix(site_geo, d["geo"]["equivalencia_glim"])
    return round(1 - sum(min(m[c], r[c] / tot) for c in GLIM_COLS), 3)


def parejas(d, sitios: pd.DataFrame) -> pd.DataFrame:
    P: dict[tuple, dict] = {}

    def get(sid, rid):
        return P.setdefault((sid, rid), {"sitio_id": sid, "region_medida": rid, "fuentes": set()})

    def put(rec, k, v):
        if v is not None and not (isinstance(v, float) and math.isnan(v)) and rec.get(k) is None:
            rec[k] = v

    for sid, s in d["topo"]["sitios"].items():
        for p in s.get("top5_tierra", []):
            r = get(sid, p["region_id"]); r["fuentes"].add("topografía")
            put(r, "d_topo", p["distancia"])
    for sid, s in d["geo"]["sitios"].items():
        for p in s.get("top5_tierra", []):
            r = get(sid, p["region_id"]); r["fuentes"].add("geología")
            put(r, "d_topo", p["distancia_topo"]); put(r, "d_geo", p["distancia_geo"])
    for sid, s in d["hielo"]["sitios"].items():
        for p in s.get("top5_tierra", []):
            r = get(sid, p["region_id"]); r["fuentes"].add("hielo")
            put(r, "d_topo", p.get("d_topo")); put(r, "d_hielo", p["d_hielo"])
    for sid, s in d["clima"]["sitios"].items():
        for p in s.get("parejas", []):
            r = get(sid, p["region_id"]); r["fuentes"].add("clima")
            put(r, "d_topo", p.get("dist_topo")); put(r, "d_clima", p["dist_clima"])
            put(r, "brecha_ts_media_C", p.get("brecha_ts_media")); put(r, "brecha_ts_min_C", p.get("brecha_ts_min"))
    for sid, s in d["cuevas"]["sitios"].items():
        for p in s.get("parejas", []):
            r = get(sid, p["id_t"]); r["fuentes"].add("cuevas")
            put(r, "d_topo", p.get("d_topo")); put(r, "d_forma_cueva", p.get("d_forma"))
            put(r, "forma_cueva", p.get("forma_parecida")); put(r, "brecha_t_interior_C", p.get("brecha_t_interior_C"))
    for sid, s in d["anort"]["sitios"].items():
        for p in s.get("top3", []):
            r = get(sid, p["id_t"]); r["fuentes"].add("anortosita")
            put(r, "d_topo", p.get("d_topo")); put(r, "d_geo", p.get("d_geo"))

    # rellenar geología e hielo donde se pueden calcular para el par
    geo_s, hielo_s, hielo_t = d["geo"]["sitios"], d["hielo"]["sitios"], d["hielo"]["tierra"]
    for (sid, rid), r in P.items():
        if r.get("d_geo") is None:
            dg = dist_geo(geo_s.get(sid), rid, d)
            if not np.isnan(dg):
                r["d_geo"] = dg; r["d_geo_calculada"] = True
        if r.get("d_hielo") is None and sid in hielo_s and rid in hielo_t:
            fs, ft = hielo_s[sid].get("f_hielo"), hielo_t[rid].get("f_permafrost")
            if fs is not None and ft is not None:
                r["d_hielo"] = round(abs(fs - ft), 3)

    df = pd.DataFrame(P.values())
    df["fuentes"] = df["fuentes"].map(lambda s: ", ".join(sorted(s)))
    df["tierra_id"] = df["region_medida"].map(lambda x: A_FICHA.get(x, x))
    df = df.merge(sitios, on="sitio_id", how="left")

    # capas evaluadas y superadas
    def evalua(r):
        res = {}
        res["topografía"] = None if pd.isna(r.get("d_topo")) else r["d_topo"] <= U_TOPO
        res["geología"] = None if pd.isna(r.get("d_geo")) else r["d_geo"] <= U_GEO
        hay_hielo = (r.get("f_hielo_sitio") or 0) >= F_HIELO_MIN
        res["hielo"] = None if (not hay_hielo or pd.isna(r.get("d_hielo"))) else r["d_hielo"] <= U_HIELO
        res["clima"] = None if pd.isna(r.get("d_clima")) else r["d_clima"] <= U_CLIMA
        fc = r.get("forma_cueva")
        res["forma de cueva"] = None if fc not in ("Sí", "No") else fc == "Sí"
        return res

    sims = {"topografía": ("d_topo", U_TOPO), "geología": ("d_geo", U_GEO), "hielo": ("d_hielo", U_HIELO),
            "clima": ("d_clima", U_CLIMA), "forma de cueva": ("d_forma_cueva", U_FORMA)}
    out = []
    for _, r in df.iterrows():
        ev = evalua(r)
        ok = [k for k, v in ev.items() if v is True]
        ko = [k for k, v in ev.items() if v is False]
        s_vals = [max(0.0, min(1.0, 1 - r[sims[k][0]] / (2 * sims[k][1]))) for k, v in ev.items() if v is not None]
        n_ok = len(ok)
        nivel = "Alta" if n_ok >= 3 else "Media" if n_ok == 2 else "Baja" if n_ok == 1 else "Sin respaldo"
        out.append(dict(capas_ok=", ".join(ok), capas_fallan=", ".join(ko), n_capas_ok=n_ok,
                        n_capas_evaluadas=len(ok) + len(ko),
                        similitud=round(float(np.mean(s_vals)), 3) if s_vals else np.nan, nivel_pareja=nivel,
                        **{f"ok_{k.split()[0]}": ("✓" if v else "✗") if v is not None else "—" for k, v in ev.items()}))
    df = pd.concat([df.reset_index(drop=True), pd.DataFrame(out)], axis=1)

    # un mismo lugar puede venir de dos ids medidos (p. ej., Lanzarote en el perfil lunar y en el marciano)
    df = (df.sort_values(["n_capas_ok", "similitud"], ascending=False)
            .drop_duplicates(["sitio_id", "tierra_id"]).reset_index(drop=True))
    return df


# ---------------------------------------------------------------- confianza de la base 1
def confianza_tierra(t: pd.DataFrame, pj: pd.DataFrame) -> pd.DataFrame:
    rank = {"Alta": 3, "Media": 2, "Baja": 1, "Sin respaldo": 0}
    pj = pj.assign(_r=pj["nivel_pareja"].map(rank))
    best = (pj.sort_values(["_r", "similitud"], ascending=False).drop_duplicates("tierra_id")
              .set_index("tierra_id"))
    cnt = pj.groupby("tierra_id")["nivel_pareja"].value_counts().unstack(fill_value=0)

    t = t.copy()
    t["mejor_nivel_pareja"] = t["id"].map(best["nivel_pareja"]).fillna("sin medir")
    t["mejor_pareja_sitio"] = t["id"].map(best["sitio"])
    t["mejor_pareja_cuerpo"] = t["id"].map(best["cuerpo"])
    t["mejor_pareja_capas_ok"] = t["id"].map(best["capas_ok"])
    for n in ("Alta", "Media"):
        t[f"n_parejas_{n.lower()}"] = t["id"].map(cnt[n] if n in cnt else {}).fillna(0).astype(int)
    t["n_sitios_evaluados"] = t["id"].map(pj.groupby("tierra_id")["sitio_id"].nunique()).fillna(0).astype(int)

    pct = t[["percentil_indice", "percentil_m1"]].max(axis=1)
    t["senal_satelite"] = np.where(pct >= 95, "sí (p ≥ 95)", np.where(pct.notna(), "no", "sin medir"))

    ev = t["verificacion"].map(PUNTOS_EVIDENCIA).fillna(0)
    datos = t["mejor_nivel_pareja"].map(PUNTOS_NIVEL).fillna(0) + (pct >= 95).astype(int)
    t["puntos_evidencia"] = ev.astype(int)
    t["puntos_datos"] = datos.astype(int)
    t["puntuacion_confianza"] = (50 * ev / 3 + 50 * datos / 4).round(0).astype(int)
    sc = t["puntuacion_confianza"]
    pareja_solida = t["mejor_nivel_pareja"].isin(["Alta", "Media"])
    # «Alta» exige además una pareja sólida (≥ 2 capas): la fuente y el satélite solos no bastan
    t["nivel_confianza"] = np.select([(sc >= 75) & pareja_solida, sc >= 50, sc >= 25],
                                     ["Alta", "Media", "Baja"], "Muy baja (hipótesis)")
    t.loc[t["lat"].isna(), "nivel_confianza"] = "Sin datos"

    # lugar conocido más cercano (para agrupar y detectar solapes)
    conocidos = t[(t["tipo_entidad"] == "sitio de la ficha") & t["lat"].notna()]
    def cercano(r):
        if pd.isna(r["lat"]):
            return pd.Series({"conocido_mas_cercano": "", "km_conocido_mas_cercano": np.nan})
        c = conocidos[conocidos["id"] != r["id"]]
        dist = c.apply(lambda x: km(r["lat"], r["lon"], x["lat"], x["lon"]), axis=1)
        i = dist.idxmin()
        return pd.Series({"conocido_mas_cercano": c.loc[i, "id"], "km_conocido_mas_cercano": round(dist[i])})
    t = pd.concat([t, t.apply(cercano, axis=1)], axis=1)

    # región medida más cercana: para los puntos sin parejas propias (M1, campos de prueba) dice dónde mirar
    regiones = t[t["tipo_entidad"] == "región del índice"]
    def region_cercana(r):
        c = regiones[regiones["id"] != r["id"]]
        dist = c.apply(lambda x: km(r["lat"], r["lon"], x["lat"], x["lon"]), axis=1)
        if pd.isna(r["lat"]) or dist.isna().all():
            return pd.Series({"region_medida_cercana": "", "km_region_medida": np.nan, "nivel_region_medida": ""})
        i = dist.idxmin()
        return pd.Series({"region_medida_cercana": c.loc[i, "id"], "km_region_medida": round(dist[i]),
                          "nivel_region_medida": c.loc[i, "mejor_nivel_pareja"]})
    t = pd.concat([t, t.apply(region_cercana, axis=1)], axis=1)
    t["orden"] = t["nivel_confianza"].map({n: i for i, n in enumerate(ORDEN_NIVEL)})
    t = t.sort_values(["orden", "puntuacion_confianza"], ascending=[True, False]).drop(columns="orden")
    return t


# ---------------------------------------------------------------- resumen por sitio y huecos
def resumen_sitios(pj: pd.DataFrame, sitios: pd.DataFrame) -> pd.DataFrame:
    rank = {"Alta": 3, "Media": 2, "Baja": 1, "Sin respaldo": 0}
    b = (pj.assign(_r=pj["nivel_pareja"].map(rank)).sort_values(["_r", "similitud"], ascending=False)
           .drop_duplicates("sitio_id").set_index("sitio_id"))
    s = sitios.copy()
    for c_out, c_in in [("mejor_nivel", "nivel_pareja"), ("mejor_tierra_id", "tierra_id"),
                        ("mejor_tierra", "tierra_nombre"), ("capas_ok", "capas_ok"), ("capas_fallan", "capas_fallan"),
                        ("similitud", "similitud"), ("d_topo", "d_topo"), ("d_geo", "d_geo")]:
        s[c_out] = s["sitio_id"].map(b[c_in])
    s["n_parejas_alta_media"] = s["sitio_id"].map(
        pj[pj["nivel_pareja"].isin(["Alta", "Media"])].groupby("sitio_id").size()).fillna(0).astype(int)
    s["mejor_nivel"] = s["mejor_nivel"].fillna("sin parejas")
    return s


def huecos(t, s, extra) -> pd.DataFrame:
    h = []
    for _, r in s[s["mejor_nivel"].isin(["Baja", "Sin respaldo", "sin parejas"])].iterrows():
        h.append(dict(tipo="sitio de la Luna/Marte sin análogo sólido", id=r["sitio_id"], nombre=r["sitio"],
                      cuerpo=r["cuerpo"], detalle=f"mejor: {r['mejor_tierra'] or '—'} ({r['mejor_nivel']}); fallan: {r['capas_fallan'] or '—'}",
                      accion="buscar un análogo de la Tierra que pase topografía y geología (o medir una capa más)"))
    for _, r in t[t["lat"].isna()].iterrows():
        h.append(dict(tipo="sitio de la ficha sin coordenadas", id=r["id"], nombre=r["nombre"], cuerpo=r["cuerpo_objetivo"],
                      detalle="candidato sin investigar", accion="buscar fuente, coordenadas y rasgo análogo; rellenar la ficha"))
    for _, r in t[t["verificacion"].isin(["pendiente", "candidato"]) & t["lat"].notna()].iterrows():
        h.append(dict(tipo="análogo sin fuente que lo confirme", id=r["id"], nombre=r["nombre"], cuerpo=r["cuerpo_objetivo"],
                      detalle=f"verificación: {r['verificacion']}; datos: {r['mejor_nivel_pareja']}",
                      accion="buscar una fuente que lo presente como análogo"))
    for _, r in t[(t["verificacion"] == "verificada") & (t["mejor_nivel_pareja"] == "sin medir")].iterrows():
        h.append(dict(tipo="análogo verificado sin medir en ninguna capa", id=r["id"], nombre=r["nombre"], cuerpo=r["cuerpo_objetivo"],
                      detalle="no aparece en las capas de parejas", accion="medirlo con topografía (círculo de 10 km) y el resto de capas"))
    top = t[(t["verificacion"] == "hipótesis") & t["mejor_nivel_pareja"].isin(["Alta", "Media"])]
    for _, r in top.iterrows():
        h.append(dict(tipo="hipótesis con buenos datos: verificar en la literatura", id=r["id"], nombre=r["nombre"],
                      cuerpo=r["cuerpo_objetivo"], detalle=f"mejor pareja {r['mejor_nivel_pareja']} con {r['mejor_pareja_sitio']}",
                      accion="buscar fuente; si la hay, pasarlo a la ficha como verificado"))
    m1 = t[(t["tipo_entidad"] == "candidato de M1") & (t.get("m1_nuevo") == "sí")]
    for _, r in m1.iterrows():
        h.append(dict(tipo="candidato nuevo de M1 sin medir por capas", id=r["id"], nombre=r["nombre"], cuerpo=r["cuerpo_objetivo"],
                      detalle=f"percentil M1 {r['percentil_m1']}", accion="medir topografía y geología en la región; buscar fuente"))
    for f in extra["fusionadas"]:
        h.append(dict(tipo="fila de la ficha fusionada", id=f["id"], nombre=f["id"], cuerpo="", detalle=f["nota"],
                      accion="borrarla de la ficha o convertirla en un sitio concreto"))
    return pd.DataFrame(h)


def geojson(t, pj) -> dict:
    feats = []
    for _, r in t[t["lat"].notna()].iterrows():
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
                      "properties": {"capa": "analogo_tierra", "id": r["id"], "nombre": r["nombre"],
                                     "tipo_entidad": r["tipo_entidad"], "verificacion": r["verificacion"],
                                     "nivel_confianza": r["nivel_confianza"], "puntuacion": int(r["puntuacion_confianza"])}})
    for _, r in pj[pj["nivel_pareja"].isin(["Alta", "Media"])].iterrows():
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(r["sitio_lon"]), float(r["sitio_lat"])]},
                      "properties": {"capa": f"sitio_{r['cuerpo']}", "sitio_id": r["sitio_id"], "sitio": r["sitio"],
                                     "tierra_id": r["tierra_id"], "tierra": r["tierra_nombre"], "nivel_pareja": r["nivel_pareja"],
                                     "similitud": None if pd.isna(r["similitud"]) else float(r["similitud"]),
                                     "nota": "coordenadas del cuerpo (Luna o Marte), no de la Tierra"}})
    return {"type": "FeatureCollection", "name": "base_analogos_v0", "features": feats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", required=True)
    ap.add_argument("--entrada", default="entrada")
    ap.add_argument("--salida", default="salida")
    a = ap.parse_args()
    d = cargar(Path(a.web), Path(a.entrada))
    out = Path(a.salida); out.mkdir(parents=True, exist_ok=True)

    sitios = sitios_luna_marte(d)
    t, extra = entidades_tierra(d)
    pj = parejas(d, sitios)

    # datos de la Tierra en cada pareja
    tt = t.set_index("id")
    pj["tierra_nombre"] = pj["tierra_id"].map(tt["nombre"]).fillna(pj["tierra_id"])
    pj["tierra_lat"] = pj["tierra_id"].map(tt["lat"])
    pj["tierra_lon"] = pj["tierra_id"].map(tt["lon"])
    pj["tierra_tipo"] = pj["tierra_id"].map(tt["tipo_entidad"])
    pj["tierra_verificacion"] = pj["tierra_id"].map(tt["verificacion"])
    sin_tierra = sorted(set(pj.loc[pj["tierra_lat"].isna(), "tierra_id"]))
    if sin_tierra:
        print("AVISO: parejas con un lugar de la Tierra sin fila en la base 1:", sin_tierra)

    t = confianza_tierra(t, pj)
    s = resumen_sitios(pj, sitios)
    h = huecos(t, s, extra)

    cols_pj = ["sitio_id", "sitio", "cuerpo", "tipo_sitio", "sitio_lat", "sitio_lon",
               "tierra_id", "tierra_nombre", "tierra_tipo", "tierra_verificacion", "tierra_lat", "tierra_lon",
               "nivel_pareja", "n_capas_ok", "n_capas_evaluadas", "similitud", "capas_ok", "capas_fallan",
               "d_topo", "d_geo", "d_hielo", "d_clima", "d_forma_cueva",
               "ok_topografía", "ok_geología", "ok_hielo", "ok_clima", "ok_forma",
               "f_hielo_sitio", "brecha_ts_media_C", "brecha_ts_min_C", "brecha_t_interior_C",
               "fuentes", "region_medida", "d_geo_calculada"]
    rank = {"Alta": 0, "Media": 1, "Baja": 2, "Sin respaldo": 3}
    pj = pj.assign(_r=pj["nivel_pareja"].map(rank)).sort_values(["cuerpo", "sitio_id", "_r", "similitud"],
                                                                 ascending=[True, True, True, False])[cols_pj]
    cols_t = ["id", "nombre", "pais_region", "lat", "lon", "coord_nota", "cuerpo_objetivo", "perfil", "tipo_entidad",
              "origen", "verificacion", "nivel_confianza", "puntuacion_confianza", "puntos_evidencia", "puntos_datos",
              "mejor_nivel_pareja", "mejor_pareja_sitio", "mejor_pareja_cuerpo", "mejor_pareja_capas_ok",
              "n_parejas_alta", "n_parejas_media", "n_sitios_evaluados", "senal_satelite", "percentil_indice",
              "percentil_m1", "m1_nuevo", "analogo_conocido_indice", "conocido_mas_cercano", "km_conocido_mas_cercano",
              "region_medida_cercana", "km_region_medida", "nivel_region_medida",
              "rasgo_analogo", "tipo_geologico", "referencia", "url", "area_km2"]
    t = t[cols_t]

    t.to_csv(out / "analogos_tierra.csv", index=False)
    pj.to_csv(out / "parejas_luna_marte.csv", index=False)
    pj[pj["nivel_pareja"].isin(["Alta", "Media"])].to_csv(out / "parejas_comprobadas.csv", index=False)
    s.to_csv(out / "sitios_luna_marte.csv", index=False)
    h.to_csv(out / "huecos.csv", index=False)
    json.dump(geojson(t, pj), open(out / "base_analogos.geojson", "w", encoding="utf-8"), ensure_ascii=False)
    print("tierra:", len(t), t["nivel_confianza"].value_counts().to_dict())
    print("parejas:", len(pj), pj["nivel_pareja"].value_counts().to_dict())
    print("sitios:", len(s), s["mejor_nivel"].value_counts().to_dict())
    print("huecos:", len(h), h["tipo"].value_counts().to_dict())


if __name__ == "__main__":
    main()
