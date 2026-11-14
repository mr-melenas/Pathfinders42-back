"""Capa usos_v0: parejas sitio (Luna/Marte) ↔ Tierra con la distancia de cada capa y su puntuación por uso.

Enfoque D («análogos según el uso de la misión»). Cada capa de 06_web guarda solo sus mejores parejas, y las
listas casi no coinciden entre capas. Aquí se unen todas (como en la base de análogos v0) y, para cada
pareja, se rellena lo que se puede calcular sin volver a Colab:

- geología: 1 − fracción de roca compartida, con la composición GLiM de cada región
  (scripts/entrada/geologia_tierra_glim.csv, copia de 04_resultados/geologia_v0). Reproduce geologia_v0.
- hielo: |f_hielo del sitio − f_permafrost de la región| (hielo_v0), solo si el sitio tiene ≥ 20 % de hielo.
- topografía, clima y forma de cueva: solo donde alguna capa ya las midió (no se inventan).

Después puntúa cada pareja para cada uso de scripts/usos.json. Escribe data/06_web/usos_v0/usos.json y
registra la capa `usos` en el manifest.

Uso: python scripts/construir_usos.py [--web data/06_web]
"""

import argparse
import csv
import json
import math
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VERSION = "usos_v0"

# Umbral de «parecido» de cada capa (los de los cierres de cada capa)
UMBRALES = {"topografia": 0.2, "geologia": 0.4, "clima": 0.2, "hielo": 0.25, "forma_cueva": 0.3}
F_HIELO_MIN = 0.2  # el hielo solo cuenta si el sitio tiene hielo (hielo_v0: 11 sitios Luna, 24 Marte)
GLIM = ["su", "ss", "sm", "py", "sc", "ev", "mt", "pa", "pi", "pb", "va", "vi", "vb", "ig"]


def leer(web: Path, rel: str | None) -> dict:
    return json.loads((web / rel).read_text(encoding="utf-8")) if rel else {}


def similitud(d: float, umbral: float) -> float:
    """1 si es igual, 0,5 en el umbral, 0 a partir del doble del umbral."""
    return max(0.0, min(1.0, 1 - d / (2 * umbral)))


def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def cargar_glim(ruta: Path) -> dict[str, dict[str, float]]:
    with ruta.open(encoding="utf-8") as f:
        return {r["region_id"]: {c: float(r[c] or 0) for c in GLIM} for r in csv.DictReader(f)}


def dist_geo(sitio_geo: dict | None, region: str, glim: dict, equivalencia: dict) -> float | None:
    """1 − fracción de roca compartida (sin agua ni «sin dato», renormalizado), como geologia_v0."""
    if not sitio_geo or region not in glim:
        return None
    r = glim[region]
    total = sum(r.values())
    if total <= 0:
        return None
    mezcla = dict.fromkeys(GLIM, 0.0)
    for clase, pesos in equivalencia.items():
        f = sitio_geo.get(f"f_{clase}") or 0
        for k, w in pesos.items():
            if k in mezcla:
                mezcla[k] += f * w
    return round(1 - sum(min(mezcla[c], r[c] / total) for c in GLIM), 3)


def unir_parejas(c: dict) -> dict[tuple[str, str], dict]:
    """Unión de las parejas de todas las capas, con lo que cada una mide."""
    P: dict[tuple[str, str], dict] = {}

    def par(sid, tid, nombre):
        r = P.setdefault((sid, tid), {"tierra_id": tid, "tierra_nombre": nombre, "fuentes": set(), "d": {}})
        if nombre and not r["tierra_nombre"]:
            r["tierra_nombre"] = nombre
        return r

    def pon(r, capa, v):
        v = _num(v)
        if v is not None and r["d"].get(capa) is None:
            r["d"][capa] = v

    for sid, s in c["topografia"].get("sitios", {}).items():
        for p in s.get("top5_tierra") or []:
            r = par(sid, p["region_id"], p.get("region"))
            r["fuentes"].add("topografia")
            pon(r, "topografia", p.get("distancia"))
    for sid, s in c["geologia"].get("sitios", {}).items():
        for p in s.get("top5_tierra") or []:
            r = par(sid, p["region_id"], p.get("region"))
            r["fuentes"].add("geologia")
            pon(r, "topografia", p.get("distancia_topo"))
            pon(r, "geologia", p.get("distancia_geo"))
    for sid, s in c["hielo"].get("sitios", {}).items():
        for p in s.get("top5_tierra") or []:
            r = par(sid, p["region_id"], p.get("region"))
            r["fuentes"].add("hielo")
            pon(r, "topografia", p.get("d_topo"))
            pon(r, "hielo", p.get("d_hielo"))
    for sid, s in c["clima"].get("sitios", {}).items():
        for p in s.get("parejas") or []:
            r = par(sid, p["region_id"], p.get("region"))
            r["fuentes"].add("clima")
            pon(r, "topografia", p.get("dist_topo"))
            pon(r, "clima", p.get("dist_clima"))
            r["brechas"] = {
                k: _num(p.get(f"brecha_{k}"))
                for k in ("ts_media", "ts_min", "ts_max", "amplitud_anual", "osc_diaria")
                if _num(p.get(f"brecha_{k}")) is not None
            }
    for sid, s in c["cuevas"].get("sitios", {}).items():
        for p in s.get("parejas") or []:
            r = par(sid, p["id_t"], p.get("nombre_t"))
            r["fuentes"].add("cuevas")
            pon(r, "topografia", p.get("d_topo"))
            pon(r, "forma_cueva", p.get("d_forma"))
            if _num(p.get("brecha_t_interior_C")) is not None:
                r.setdefault("brechas", {})["t_interior"] = p["brecha_t_interior_C"]
    for sid, s in c["anortosita"].get("sitios", {}).items():
        for p in s.get("top3") or []:
            r = par(sid, p["id_t"], p.get("lugar"))
            r["fuentes"].add("anortosita")
            pon(r, "topografia", p.get("d_topo"))
            pon(r, "geologia", p.get("d_geo"))
    return P


def puntuar(d: dict, uso: dict) -> dict | None:
    """Puntuación de una pareja para un uso, o None si le falta una capa obligatoria."""
    pesos = {k: w for k, w in uso["pesos"].items() if w}
    if any(d.get(k) is None for k in uso["requiere"]):
        return None
    con_dato = {k: w for k, w in pesos.items() if d.get(k) is not None}
    if not con_dato:
        return None
    n_ok = sum(d[k] <= UMBRALES[k] for k in con_dato)
    s = sum(w * similitud(d[k], UMBRALES[k]) for k, w in con_dato.items()) / sum(con_dato.values())
    return {
        "puntuacion": round(s, 3),
        "cobertura": round(sum(con_dato.values()) / sum(pesos.values()), 2),
        "apta": all(d[k] <= UMBRALES[k] for k in uso["requiere"]) and n_ok >= uso.get("min_capas_ok", 0),
        "n_ok": n_ok,
    }


def construir(web: Path, config: dict, glim: dict) -> dict:
    manifest = leer(web, "manifest.json")
    capas = manifest["capas"]
    c = {
        "topografia": leer(web, capas["topografia_sitios"]["archivo"]),
        "geologia": leer(web, capas["geologia"]["archivo"]),
        "hielo": leer(web, capas["hielo"]["archivo"]),
        "clima": leer(web, capas["clima"]["archivo"]),
        "cuevas": leer(web, capas["cuevas_v2"]["archivo"]),
        "anortosita": leer(web, capas["anortosita"]["archivo"]),
    }
    geo_s, hielo_s = c["geologia"].get("sitios", {}), c["hielo"].get("sitios", {})
    hielo_t = c["hielo"].get("tierra", {})
    equivalencia = c["geologia"]["equivalencia_glim"]
    # Coordenadas de la Tierra que dan las capas (regiones, cuevas y anortosita)
    coords = {k: (v.get("lat_c"), v.get("lon_c")) for k, v in hielo_t.items()}
    for capa in ("cuevas", "anortosita"):
        coords.update({k: (v.get("lat"), v.get("lon")) for k, v in c[capa].get("tierra", {}).items()})

    sitios_geo = leer(web, capas["sitios"]["archivo"]).get("features", [])
    sitios_geo += leer(web, capas["cuevas_v2"]["sitios"]).get("features", [])
    tipo = {f["properties"]["id"]: f["properties"].get("tipo", "") for f in sitios_geo}

    salida: dict[str, dict] = {}
    for (sid, tid), r in unir_parejas(c).items():
        if sid not in tipo:
            continue
        d = r["d"]
        f_hielo = _num((hielo_s.get(sid) or {}).get("f_hielo"))
        con_hielo = (f_hielo or 0) >= F_HIELO_MIN
        if d.get("geologia") is None:
            dg = dist_geo(geo_s.get(sid), tid, glim, equivalencia)
            if dg is not None:
                d["geologia"] = dg
        if d.get("hielo") is None and con_hielo and tid in hielo_t:
            fp = _num(hielo_t[tid].get("f_permafrost"))
            if fp is not None:
                d["hielo"] = round(abs(f_hielo - fp), 3)
        if not con_hielo:
            d.pop("hielo", None)  # «sin hielo frente a sin permafrost» no prueba nada

        es_cueva = tipo[sid].startswith("cueva")
        usos = {}
        for uso in config["usos"]:
            if uso["solo_sitios"] == "con_hielo" and not con_hielo:
                continue
            if uso["solo_sitios"] == "cuevas" and not es_cueva:
                continue
            p = puntuar(d, uso)
            if p:
                usos[uso["id"]] = p
        lat, lon = coords.get(tid, (None, None))
        sitio = salida.setdefault(sid, {"f_hielo": f_hielo, "con_hielo": con_hielo, "parejas": []})
        sitio["parejas"].append(
            {
                "tierra_id": tid,
                "tierra_nombre": r["tierra_nombre"] or tid,
                "tierra_lat": _num(lat),
                "tierra_lon": _num(lon),
                "distancias": {k: d[k] for k in UMBRALES if d.get(k) is not None},
                "funciona": [k for k in UMBRALES if d.get(k) is not None and d[k] <= UMBRALES[k]],
                "falla": [k for k in UMBRALES if d.get(k) is not None and d[k] > UMBRALES[k]],
                "brechas_C": r.get("brechas") or {},
                "fuentes": sorted(r["fuentes"]),
                "usos": usos,
            }
        )
    # Un mismo lugar puede venir con dos nombres de región iguales: se queda el que más capas mide
    for s in salida.values():
        vistos: dict[str, dict] = {}
        for p in sorted(s["parejas"], key=lambda p: -len(p["distancias"])):
            vistos.setdefault(p["tierra_nombre"], p)
        s["parejas"] = sorted(vistos.values(), key=lambda p: p["tierra_id"])

    return {
        "version": VERSION,
        "generado": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "umbrales": UMBRALES,
        "f_hielo_min": F_HIELO_MIN,
        "usos": config["usos"],
        "unidades": {
            "distancias": "0 = igual, 1 = nada parecido; parecido si ≤ umbral de la capa",
            "puntuacion": "media ponderada de similitudes (1 igual, 0,5 en el umbral, 0 al doble)",
            "cobertura": "fracción del peso del uso con dato en esta pareja",
            "apta": "pasa el umbral en todas las capas obligatorias del uso",
            "brechas_C": "Tierra − sitio, en °C (clima y temperatura interior de cuevas)",
        },
        "nota": (
            "Unión de los top de cada capa. Geología e hielo se recalculan para todas las parejas; "
            "topografía, clima y forma de cueva solo existen donde alguna capa ya las midió. "
            "El clima solo está en su top 5: el uso «pruebas térmicas» solo ve esas parejas."
        ),
        "sitios": salida,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--web", default=str(RAIZ / "data" / "06_web"))
    ap.add_argument("--config", default=str(RAIZ / "scripts" / "usos.json"))
    ap.add_argument("--glim", default=str(RAIZ / "scripts" / "entrada" / "geologia_tierra_glim.csv"))
    a = ap.parse_args()
    web = Path(a.web)
    capa = construir(web, json.loads(Path(a.config).read_text(encoding="utf-8")), cargar_glim(Path(a.glim)))
    destino = web / VERSION / "usos.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(capa, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    ruta_m = web / "manifest.json"
    manifest = json.loads(ruta_m.read_text(encoding="utf-8"))
    manifest["capas"]["usos"] = {"version": VERSION, "carpeta": VERSION, "archivo": f"{VERSION}/usos.json"}
    ruta_m.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    n = sum(len(s["parejas"]) for s in capa["sitios"].values())
    print(f"{destino}: {len(capa['sitios'])} sitios, {n} parejas, {destino.stat().st_size / 1024:.0f} kB")
    for uso in capa["usos"]:
        aptas = {
            sid
            for sid, s in capa["sitios"].items()
            for p in s["parejas"]
            if p["usos"].get(uso["id"], {}).get("apta")
        }
        con = {sid for sid, s in capa["sitios"].items() for p in s["parejas"] if uso["id"] in p["usos"]}
        print(f"  {uso['id']:<18} sitios evaluados {len(con):>3} · con pareja apta {len(aptas):>3}")


if __name__ == "__main__":
    main()
