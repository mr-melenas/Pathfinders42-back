"""Salida de M1 para la web: regiones candidatas, explicación SHAP, mapa PNG y manifest."""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from modelos.m1 import rejilla

# Misma rampa de color que el resto de índices (leyenda.json de v1.3), pero desde el percentil 80:
# lo que interesa de M1 es el 20 % superior.
LEYENDA = {
    "variable": "percentil de la puntuación de M1 dentro de la rejilla",
    "min": 80,
    "max": 100,
    "transparente_por_debajo_de": 80,
    "opacidad": 0.85,
    "paradas": [
        {"valor": 80, "color": "#ffffcc"},
        {"valor": 84, "color": "#fee187"},
        {"valor": 88, "color": "#feab49"},
        {"valor": 92, "color": "#fc5b2e"},
        {"valor": 96, "color": "#d41020"},
        {"valor": 100, "color": "#800026"},
    ],
}
LADO_PNG = 1152  # igual que los índices de v1.3
MAX_LAT_MERCATOR = 85.0511287798
N_MODELOS_SHAP = 25


class Explicador:
    """SHAP de un conjunto de bolsas: media de los valores SHAP de varios modelos LightGBM.

    Los valores están en log-odds (la escala interna del modelo): positivo = empuja hacia «análogo».
    """

    def __init__(self, modelos: list, variables: list[str]):
        import shap

        self.variables = variables
        self.explicadores = [shap.TreeExplainer(m) for m in modelos[:N_MODELOS_SHAP]]

    def shap(self, X: np.ndarray) -> np.ndarray:
        valores = []
        for e in self.explicadores:
            v = e.shap_values(X)
            if isinstance(v, list):  # versiones antiguas de shap: [clase 0, clase 1]
                v = v[1]
            valores.append(np.asarray(v))
        return np.mean(valores, axis=0)

    def importancia(self, X: np.ndarray) -> list[dict]:
        media = np.abs(self.shap(X)).mean(axis=0)
        orden = np.argsort(-media)
        return [{"variable": self.variables[i], "media_abs_shap": round(float(media[i]), 3)} for i in orden]

    def explicar(self, x: np.ndarray, n: int = 4) -> list[dict]:
        v = self.shap(x.reshape(1, -1))[0]
        orden = np.argsort(-np.abs(v))[:n]
        return [
            {
                "variable": self.variables[i],
                "valor": None if np.isnan(x[i]) else round(float(x[i]), 3),
                "contribucion": round(float(v[i]), 3),
                "sentido": "a favor" if v[i] > 0 else "en contra",
            }
            for i in orden
        ]


def regiones_candidatas(celdas: pd.DataFrame, s_sin_pos: np.ndarray, pct: np.ndarray, umbral: float) -> list:
    """Agrupa en regiones las celdas vecinas (8 vecinas) por encima del percentil ``umbral``.

    La mejor celda de cada región se elige entre las que no son positivas (su puntuación es honesta).
    Orden: de mayor a menor puntuación de la mejor celda.
    """
    ncol = round(360 / rejilla.PASO_LON)
    sel = {
        (int(i), int(j)): k
        for k, (i, j) in enumerate(zip(celdas.i, celdas.j, strict=True))
        if pct[k] >= umbral
    }
    vistos: set = set()
    regiones = []
    for inicio in sel:
        if inicio in vistos:
            continue
        pila, miembros = [inicio], []
        vistos.add(inicio)
        while pila:
            i, j = pila.pop()
            miembros.append(sel[(i, j)])
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    v = (i + di, (j + dj) % ncol)
                    if v in sel and v not in vistos:
                        vistos.add(v)
                        pila.append(v)
        honestas = [k for k in miembros if not np.isnan(s_sin_pos[k])]
        if not honestas:
            continue
        mejor = max(honestas, key=lambda k: s_sin_pos[k])
        regiones.append({"celdas": miembros, "mejor": mejor, "max": float(s_sin_pos[mejor])})
    return sorted(regiones, key=lambda r: (-r["max"], -len(r["celdas"])))


def separar(regiones: list, lat: np.ndarray, lon: np.ndarray, km: float) -> list:
    """Se queda con una región de cada zona: descarta las que están a < km de una mejor ya elegida."""
    elegidas: list = []
    for r in regiones:
        k = r["mejor"]
        if all(
            rejilla.haversine_km(lat[k], lon[k], lat[e["mejor"]], lon[e["mejor"]]) >= km for e in elegidas
        ):
            elegidas.append(r)
    return elegidas


def nombre_lugar(lat: float, lon: float) -> dict:
    """Nombre legible a partir de la población más cercana (GeoNames, sin red: reverse_geocoder)."""
    import reverse_geocoder as rg

    r = rg.search([(lat, lon)], mode=1, verbose=False)[0]
    d = float(rejilla.haversine_km(lat, lon, float(r["lat"]), float(r["lon"])))
    lugar = f"{r['name']} ({r['admin1']}, {r['cc']})" if r["admin1"] else f"{r['name']} ({r['cc']})"
    texto = f"Cerca de {lugar}" if d < 50 else f"A {round(d, -1):.0f} km de {lugar}"
    return {
        "nombre": texto,
        "pais_iso": r["cc"],
        "referencia": {"poblacion": r["name"], "region": r["admin1"], "dist_km": int(round(d))},
    }


def area_celda_km2(lat: float) -> float:
    return (rejilla.PASO_LAT * 111.32) * (rejilla.PASO_LON * 111.32 * math.cos(math.radians(lat)))


def feature_region(celdas: pd.DataFrame, miembros: list[int], cand: dict) -> dict:
    """Región como MultiPolygon de los rectángulos de sus celdas (GeoJSON, lon/lat)."""
    hl, hn = rejilla.PASO_LAT / 2, rejilla.PASO_LON / 2
    poligonos = []
    for k in miembros:
        la, lo = float(celdas.lat.iloc[k]), float(celdas.lon.iloc[k])
        anillo = [
            [lo - hn, la - hl],
            [lo + hn, la - hl],
            [lo + hn, la + hl],
            [lo - hn, la + hl],
            [lo - hn, la - hl],
        ]
        poligonos.append([[[round(x, 4), round(y, 4)] for x, y in anillo]])
    props = {
        k: cand[k]
        for k in ("id", "familia", "rango", "nombre", "puntuacion", "percentil", "nuevo", "lat", "lon")
    }
    return {
        "type": "Feature",
        "geometry": {"type": "MultiPolygon", "coordinates": poligonos},
        "properties": props,
    }


def _color(valor: float) -> tuple[int, int, int, int]:
    paradas = LEYENDA["paradas"]
    if valor < LEYENDA["transparente_por_debajo_de"]:
        return (0, 0, 0, 0)
    for a, b in zip(paradas, paradas[1:], strict=False):
        if valor <= b["valor"]:
            t = (valor - a["valor"]) / (b["valor"] - a["valor"])
            ca = [int(a["color"][i : i + 2], 16) for i in (1, 3, 5)]
            cb = [int(b["color"][i : i + 2], 16) for i in (1, 3, 5)]
            return (
                *(round(x + t * (y - x)) for x, y in zip(ca, cb, strict=True)),
                round(255 * LEYENDA["opacidad"]),
            )
    return (*[int(paradas[-1]["color"][i : i + 2], 16) for i in (1, 3, 5)], round(255 * LEYENDA["opacidad"]))


def mapa_png(celdas: pd.DataFrame, pct: np.ndarray, ruta: Path) -> None:
    """PNG en Web Mercator con los mismos límites que los índices (EPSG:3857, ±85,05°)."""
    from PIL import Image

    ncol = round(360 / rejilla.PASO_LON)
    valor = np.full((round(180 / rejilla.PASO_LAT) + 1, ncol), np.nan)
    valor[celdas.i.to_numpy(), celdas.j.to_numpy()] = pct
    y = (np.arange(LADO_PNG) + 0.5) / LADO_PNG
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * y))))
    x = (np.arange(LADO_PNG) + 0.5) / LADO_PNG
    lon = -180 + 360 * x
    ii, jj = rejilla.indices(lat, lon)
    rejilla_px = valor[ii[:, None], jj[None, :]]
    rgba = np.zeros((LADO_PNG, LADO_PNG, 4), dtype=np.uint8)
    for r, c in zip(*np.nonzero(rejilla_px >= LEYENDA["transparente_por_debajo_de"]), strict=True):
        rgba[r, c] = _color(float(rejilla_px[r, c]))
    Image.fromarray(rgba, "RGBA").save(ruta, optimize=True)


def escribir_json(ruta: Path, obj) -> None:
    ruta.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def registrar_en_manifest(datos: Path, version: str, familias: list[str]) -> None:
    """Añade (o actualiza) la capa ``m1`` en manifest.json sin tocar el resto."""
    ruta = datos / "manifest.json"
    manifest = json.loads(ruta.read_text(encoding="utf-8"))
    manifest.setdefault("capas", {})["m1"] = {
        "version": version,
        "carpeta": version,
        "archivo": f"{version}/candidatos.json",
        "geojson": f"{version}/candidatos.geojson",
        "leyenda": f"{version}/leyenda.json",
        "mapas": {f: f"{version}/mapa_{f}.png" for f in familias},
    }
    escribir_json(ruta, manifest)
