"""Tabla de entrenamiento de M1: una fila por celda de tierra de la rejilla MERRA-2 (0,5° x 0,625°).

Une dos productos que ya calcularon los notebooks de Colab:

- ``v1.3/celdas.parquet`` (índice de Marte): clima MERRA-2 y vegetación VIIRS por celda de ~50 km.
- ``luna_v0.3/celdas.parquet`` (índice de la Luna): índice de emisividad térmica y % de roca volcánica
  (GLiM) en celdas finas de 0,05°. Aquí se agregan a la celda gruesa.

No se usa el percentil del índice de Marte como variable: sería enseñar al modelo a copiar el índice
hecho a mano. Tampoco lat/lon: el modelo memorizaría «cerca de un análogo» en vez de «se parece a uno».
"""

from pathlib import Path

import numpy as np
import pandas as pd

PASO_LAT = 0.5
PASO_LON = 0.625
CELDAS_FINAS_POR_GRUESA = (PASO_LAT / 0.05) * (PASO_LON / 0.05)  # 10 x 12,5 = 125
RADIO_TIERRA_KM = 6371.0

# Nombre de la variable → descripción corta (se exporta para el front y para explicar el SHAP)
VARIABLES: dict[str, str] = {
    "T_media": "temperatura media anual del aire (°C, MERRA-2)",
    "T_frio": "temperatura media del mes más frío (°C)",
    "T_calido": "temperatura media del mes más cálido (°C)",
    "amplitud_termica": "mes cálido menos mes frío (°C)",
    "P_anual": "precipitación anual (mm)",
    "elevacion": "elevación media de la celda (m)",
    "rugosidad": "desviación de la elevación con las 8 celdas vecinas (m): relieve a ~150 km",
    "ndvi_max": "NDVI máximo (VIIRS): cuánta vegetación hay",
    "frac_desnudo": "fracción de suelo desnudo (NDVI < 0,15)",
    "emis_p_max": "percentil máximo del índice de emisividad lunar dentro de la celda (0 si no hay dominio)",
    "frac_emis_p90": "fracción de la celda con índice de emisividad ≥ p90",
    "frac_volcanica": "fracción de la celda con ≥ 50 % de roca volcánica (GLiM) en suelo desnudo",
}


def indices(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fila y columna de la celda gruesa que contiene cada punto (centros en múltiplos del paso)."""
    i = np.round((np.asarray(lat) + 90) / PASO_LAT).astype(int)
    j = np.round((np.asarray(lon) + 180) / PASO_LON).astype(int) % round(360 / PASO_LON)
    return i, j


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * RADIO_TIERRA_KM * np.arcsin(np.sqrt(a))


def _rugosidad(celdas: pd.DataFrame) -> pd.Series:
    """Desviación típica de la elevación en la ventana 3x3 (solo celdas de tierra que existan)."""
    elev = dict(zip(zip(celdas.i, celdas.j, strict=True), celdas.elevacion, strict=True))
    ncol = round(360 / PASO_LON)
    salida = []
    for i, j in zip(celdas.i, celdas.j, strict=True):
        vals = [
            elev[(i + di, (j + dj) % ncol)]
            for di in (-1, 0, 1)
            for dj in (-1, 0, 1)
            if (i + di, (j + dj) % ncol) in elev
        ]
        salida.append(float(np.std(vals)) if len(vals) >= 3 else np.nan)
    return pd.Series(salida, index=celdas.index)


def construir(datos: Path) -> pd.DataFrame:
    """Tabla celda x variables. ``datos`` es la carpeta 06_web (data/06_web o la de Drive)."""
    marte = pd.read_parquet(datos / "v1.3" / "celdas.parquet")
    celdas = marte[
        ["lat", "lon", "T_media", "T_frio", "T_calido", "P_anual", "elevacion", "ndvi_max", "frac_desnudo"]
    ].copy()
    celdas[["lat", "lon"]] = celdas[["lat", "lon"]].astype(float)
    celdas["amplitud_termica"] = celdas.T_calido - celdas.T_frio
    celdas["i"], celdas["j"] = indices(celdas.lat, celdas.lon)
    celdas["rugosidad"] = _rugosidad(celdas)

    luna = pd.read_parquet(datos / "luna_v0.3" / "celdas.parquet")
    luna["i"], luna["j"] = indices(luna.lat, luna.lon)
    agg = luna.groupby(["i", "j"]).agg(
        emis_p_max=("percentil", "max"),
        n_p90=("percentil", lambda s: int((s >= 90).sum())),
        n_volc=("glim_volcanica_pct", lambda s: int((s >= 50).sum())),
    )
    agg["frac_emis_p90"] = (agg.n_p90 / CELDAS_FINAS_POR_GRUESA).clip(upper=1)
    agg["frac_volcanica"] = (agg.n_volc / CELDAS_FINAS_POR_GRUESA).clip(upper=1)
    celdas = celdas.merge(agg[["emis_p_max", "frac_emis_p90", "frac_volcanica"]], on=["i", "j"], how="left")
    # Sin celdas finas = fuera del dominio del índice lunar (vegetación, nieve) o percentil < 50
    celdas[["emis_p_max", "frac_emis_p90", "frac_volcanica"]] = celdas[
        ["emis_p_max", "frac_emis_p90", "frac_volcanica"]
    ].fillna(0.0)
    celdas["id_celda"] = [f"c{i:03d}_{j:03d}" for i, j in zip(celdas.i, celdas.j, strict=True)]
    return celdas.reset_index(drop=True)


def asignar_positivos(celdas: pd.DataFrame, positivos: pd.DataFrame, max_km: float = 60.0) -> pd.DataFrame:
    """Celda más cercana de cada análogo (si está a ≤ max_km; si no, el análogo no entra)."""
    filas = []
    for p in positivos.itertuples():
        d = haversine_km(p.lat, p.lon, celdas.lat.to_numpy(), celdas.lon.to_numpy())
        k = int(np.argmin(d))
        filas.append(
            {"id": p.id, "idx_celda": k if d[k] <= max_km else -1, "dist_celda_km": round(float(d[k]), 1)}
        )
    return positivos.merge(pd.DataFrame(filas), on="id")
