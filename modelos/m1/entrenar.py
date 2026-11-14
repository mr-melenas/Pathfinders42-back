"""M1 · buscador de análogos nuevos. Entrena, valida y exporta a ``<datos>/m1_v0``.

Uso (desde la raíz del repo, con ``pip install -e ".[ml]"``):

    python -m modelos.m1.entrenar                      # datos en data/06_web
    python -m modelos.m1.entrenar --datos "/content/drive/MyDrive/Hackathon Nasa/06_web"   # en Colab

Escribe ``m1_v0/`` (candidatos.json, candidatos.geojson, mapa_<familia>.png, leyenda.json) y registra la
capa ``m1`` en ``manifest.json`` de esa misma carpeta. No se ejecuta en el servidor: la API solo lee la
salida. Tarda ~1–2 minutos en CPU. Todo es determinista (semilla fija).

Explicación del método, decisiones y resultados: docs/m1_buscador_analogos.md
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from modelos.m1 import exportar, pu, rejilla

RAIZ = Path(__file__).resolve().parents[2]
VERSION = "m1_v0"
SEMILLA = 42
N_BOLSAS = 100
N_BOLSAS_VALIDACION = 30
RATIO = 10  # negativos provisionales por positivo en cada bolsa
BUFFER_KM = 150  # alrededor de cada positivo: no se usa como negativo provisional
GRUPO_KM = 300  # positivos a menos de esta distancia se dejan fuera juntos en la validación
NUEVO_KM = 200  # un candidato es «nuevo» si no hay ningún análogo conocido a menos de esta distancia
SEPARACION_KM = 500  # distancia mínima entre candidatos, para que la lista no se amontone en un sitio
PERCENTIL_CANDIDATO = 99.0  # celdas del 1 % superior forman las regiones candidatas
N_CANDIDATOS = 20

FAMILIAS: dict[str, dict] = {
    "marte_seco": {
        "nombre": "Marte seco (desiertos fríos y áridos)",
        "descripcion": (
            "Desiertos polares, de altura e hiperáridos: muy secos, con poca o ninguna vegetación y "
            "temperaturas extremas. Análogos de las llanuras y depósitos salinos de Marte."
        ),
        "variables": [
            "T_media",
            "T_frio",
            "T_calido",
            "amplitud_termica",
            "P_anual",
            "elevacion",
            "rugosidad",
            "ndvi_max",
            "frac_desnudo",
        ],
        # Conocimiento del dominio: más lluvia o más vegetación nunca hace un sitio más «marciano»
        "monotonia": {"P_anual": -1, "ndvi_max": -1, "frac_desnudo": 1},
    },
    "volcanico_basaltico": {
        "nombre": "Basalto desnudo (Luna y Marte volcánicos)",
        "descripcion": (
            "Coladas, campos volcánicos y tubos de lava de basalto poco cubierto por vegetación. "
            "Análogos de los mares lunares, los tubos de lava y las provincias volcánicas de Marte."
        ),
        # Solo roca y superficie. Ni clima ni relieve: Hawái e Islandia son húmedos y montañosos a escala
        # de 50 km, y el modelo aprendía «montaña con vegetación» en vez de «basalto desnudo» (ver doc).
        "variables": ["emis_p_max", "frac_emis_p90", "frac_volcanica", "ndvi_max", "frac_desnudo"],
        "monotonia": {
            "emis_p_max": 1,
            "frac_emis_p90": 1,
            "frac_volcanica": 1,
            "ndvi_max": -1,
            "frac_desnudo": 1,
        },
    },
}

# Lugares que no deberían parecerse a ninguna familia (o a una sí y a otra no: se comenta en el doc)
CONTROLES = {
    "Amazonía central": (-3.0, -60.0),
    "Cuenca del Congo": (0.0, 20.0),
    "Delta del Ganges (Bangladés)": (24.0, 90.0),
    "París": (48.85, 2.35),
    "Borneo": (1.0, 114.0),
    "Pampa húmeda": (-34.0, -61.0),
    "Taiga de Siberia": (60.0, 100.0),
    "Gran Erg Occidental (arena, Sáhara)": (30.0, 1.0),
}


def _grupos(celdas: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> list[list[int]]:
    """Agrupa las celdas positivas cercanas (≤ GRUPO_KM) para dejarlas fuera a la vez."""
    grupos: list[list[int]] = []
    for k in celdas:
        for g in grupos:
            if any(rejilla.haversine_km(lat[k], lon[k], lat[o], lon[o]) <= GRUPO_KM for o in g):
                g.append(int(k))
                break
        else:
            grupos.append([int(k)])
    return grupos


def _buffer(idxs, lat, lon) -> np.ndarray:
    m = np.zeros(len(lat), dtype=bool)
    for k in idxs:
        m |= rejilla.haversine_km(lat[k], lon[k], lat, lon) <= BUFFER_KM
    return m


def _celda_de(lat0: float, lon0: float, lat, lon) -> int:
    return int(np.argmin(rejilla.haversine_km(lat0, lon0, lat, lon)))


def _params(cfg: dict) -> dict:
    """Restricciones monótonas de LightGBM: +1 = la puntuación solo puede subir con la variable."""
    return {"monotone_constraints": [cfg.get("monotonia", {}).get(v, 0) for v in cfg["variables"]]}


def validar(X, celdas_pos, lat, lon, base: np.ndarray, ids_por_celda: dict, params: dict) -> dict:
    """Validación dejando fuera cada grupo de análogos: ¿vuelve a salir arriba sin haberlo visto?

    ``base`` es la puntuación de referencia (el índice hecho a mano) para comparar en igualdad.
    """
    filas = []
    for g in _grupos(celdas_pos, lat, lon):
        entreno = np.array([k for k in celdas_pos if k not in g])
        res = pu.entrenar_pu(
            X,
            entreno,
            _buffer(entreno, lat, lon),
            n_bolsas=N_BOLSAS_VALIDACION,
            ratio=RATIO,
            semilla=SEMILLA,
            params=params,
        )
        s = res.puntuacion.copy()
        s[entreno] = np.nan
        p_m1 = pu.percentil(s, s[g])
        p_base = pu.percentil(base, base[g])
        for k, a, b in zip(g, p_m1, p_base, strict=True):
            filas.append(
                {
                    "analogos": ids_por_celda[k],
                    "percentil_m1": round(float(a), 1),
                    "percentil_indice": round(float(b), 1),
                }
            )
    m1 = np.array([f["percentil_m1"] for f in filas])
    bs = np.array([f["percentil_indice"] for f in filas])
    return {
        "metodo": f"dejar fuera cada grupo de análogos (≤ {GRUPO_KM} km), {N_BOLSAS_VALIDACION} bolsas",
        "celdas": filas,
        "mediana_m1": round(float(np.median(m1)), 1),
        "minimo_m1": round(float(m1.min()), 1),
        "top5_m1": round(float((m1 >= 95).mean()), 2),
        "top10_m1": round(float((m1 >= 90).mean()), 2),
        "mediana_indice": round(float(np.median(bs)), 1),
        "top10_indice": round(float((bs >= 90).mean()), 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datos", type=Path, default=RAIZ / "data" / "06_web", help="Carpeta 06_web")
    ap.add_argument("--positivos", type=Path, default=Path(__file__).with_name("positivos.csv"))
    args = ap.parse_args()
    datos = args.datos.resolve()
    salida = datos / VERSION
    salida.mkdir(exist_ok=True)

    celdas = rejilla.construir(datos)
    positivos = rejilla.asignar_positivos(celdas, pd.read_csv(args.positivos, keep_default_na=False))
    lat, lon = celdas.lat.to_numpy(), celdas.lon.to_numpy()
    print(f"Rejilla: {len(celdas)} celdas · {len(rejilla.VARIABLES)} variables")

    # Índices hechos a mano, como referencia: el de Marte (percentil dentro de su perfil) y el lunar
    marte = pd.read_parquet(datos / "v1.3" / "celdas.parquet")
    bases = {
        "marte_seco": marte.percentil.to_numpy(float),
        "volcanico_basaltico": celdas.emis_p_max.to_numpy(float),
    }
    prueba_ciega_luna = [
        (f["properties"]["nombre"], *f["geometry"]["coordinates"][::-1])
        for f in json.loads((datos / "luna_v0.3" / "analogos.geojson").read_text(encoding="utf-8"))[
            "features"
        ]
        if f["properties"].get("tipo") == "volcanico_prueba"
    ]
    conocidos = positivos[positivos.lat.astype(str) != ""]  # todos los análogos con coordenadas

    resultado: dict = {
        "version": VERSION,
        "generado": datetime.now().isoformat(timespec="seconds"),
        "modelo": {
            "metodo": "Aprendizaje PU con bagging (Mordelet y Vert, 2014) y LightGBM; explicación con SHAP",
            "lightgbm": pu.PARAMS_LGBM,
            "n_bolsas": N_BOLSAS,
            "negativos_por_positivo": RATIO,
            "zona_amortiguacion_km": BUFFER_KM,
            "separacion_candidatos_km": SEPARACION_KM,
            "nuevo_si_no_hay_analogo_a_km": NUEVO_KM,
            "semilla": SEMILLA,
            "nota": "puntuacion ordena celdas (0–1); no es una probabilidad calibrada",
        },
        "rejilla": {
            "resolucion": "0.5° lat x 0.625° lon (MERRA-2, ~50 km)",
            "n_celdas": len(celdas),
            "nota": "solo tierra sin hielo entre 55° S y 84° N: no incluye la Antártida ni islas pequeñas",
        },
        "variables": rejilla.VARIABLES,
        "familias": {},
    }
    geo_features: list[dict] = []
    puntuaciones: dict[str, np.ndarray] = {}

    for fam, cfg in FAMILIAS.items():
        print(f"\n== {fam}")
        X = celdas[cfg["variables"]].to_numpy(float)
        q = positivos[(positivos.familia == fam) & (positivos.idx_celda >= 0)]
        fuera = positivos[(positivos.familia == fam) & (positivos.idx_celda < 0)]
        celdas_pos = np.unique(q.idx_celda.to_numpy())
        ids_por_celda = {int(k): q[q.idx_celda == k].id.tolist() for k in celdas_pos}

        params = _params(cfg)
        val = validar(X, celdas_pos, lat, lon, bases[fam], ids_por_celda, params)
        print(f"  validación: mediana M1 {val['mediana_m1']} · índice {val['mediana_indice']}")

        final = pu.entrenar_pu(X, celdas_pos, _buffer(celdas_pos, lat, lon), N_BOLSAS, RATIO, SEMILLA, params)
        s = final.puntuacion.copy()
        s_pos = pu.predecir(final.modelos, X[celdas_pos])  # vistos en todas las bolsas: valor optimista
        s_sin_pos = s.copy()
        s_sin_pos[celdas_pos] = np.nan
        s[celdas_pos] = s_pos
        puntuaciones[fam] = s
        pct = pu.percentil(s_sin_pos, s)

        val["controles"] = [
            {
                "nombre": n,
                "lat": la,
                "lon": lo,
                "percentil_m1": round(float(pct[_celda_de(la, lo, lat, lon)]), 1),
            }
            for n, (la, lo) in CONTROLES.items()
        ]
        if fam == "volcanico_basaltico":
            ciegos = [*prueba_ciega_luna, ("Tubos de lava de Undara (candidato)", -18.25, 144.6)]
            val["prueba_ciega"] = [
                {
                    "nombre": n,
                    "lat": la,
                    "lon": lo,
                    "percentil_m1": round(float(pct[_celda_de(la, lo, lat, lon)]), 1),
                }
                for n, la, lo in ciegos
            ]

        expl = exportar.Explicador(final.modelos, cfg["variables"])
        muestra = np.random.default_rng(SEMILLA).choice(len(X), size=min(5000, len(X)), replace=False)
        importancia = expl.importancia(X[muestra])

        regiones = exportar.separar(
            exportar.regiones_candidatas(celdas, s_sin_pos, pct, PERCENTIL_CANDIDATO), lat, lon, SEPARACION_KM
        )[:N_CANDIDATOS]
        candidatos = []
        for rango, reg in enumerate(regiones, start=1):
            k = reg["mejor"]
            d_conocidos = rejilla.haversine_km(
                lat[k], lon[k], conocidos.lat.astype(float).to_numpy(), conocidos.lon.astype(float).to_numpy()
            )
            j = int(np.argmin(d_conocidos))
            cid = f"{fam}-{rango}"
            cand = {
                "id": cid,
                "familia": fam,
                "rango": rango,
                **exportar.nombre_lugar(lat[k], lon[k]),
                "lat": float(lat[k]),
                "lon": float(lon[k]),
                "puntuacion": round(float(s[k]), 3),
                "percentil": round(float(pct[k]), 2),
                "n_celdas": len(reg["celdas"]),
                "area_km2": int(round(sum(exportar.area_celda_km2(lat[c]) for c in reg["celdas"]), -2)),
                "nuevo": bool(d_conocidos[j] > NUEVO_KM),
                "analogo_cercano": {
                    "id": conocidos.id.iloc[j],
                    "nombre": conocidos.nombre.iloc[j],
                    "dist_km": int(round(d_conocidos[j])),
                },
                "variables": {
                    v: (None if np.isnan(celdas[v].iloc[k]) else round(float(celdas[v].iloc[k]), 3))
                    for v in cfg["variables"]
                },
                "explicacion": expl.explicar(X[k]),
            }
            candidatos.append(cand)
            geo_features.append(exportar.feature_region(celdas, reg["celdas"], cand))
        nuevos = sum(c["nuevo"] for c in candidatos)
        print(f"  {len(candidatos)} regiones candidatas, {nuevos} nuevas")

        mapa = f"{VERSION}/mapa_{fam}.png"
        exportar.mapa_png(celdas, pct, datos / mapa)
        resultado["familias"][fam] = {
            "id": fam,
            "nombre": cfg["nombre"],
            "descripcion": cfg["descripcion"],
            "variables": cfg["variables"],
            "monotonia": cfg.get("monotonia", {}),
            "positivos": [
                {
                    "id": r.id,
                    "nombre": r.nombre,
                    "lat": float(r.lat),
                    "lon": float(r.lon),
                    "id_celda": celdas.id_celda.iloc[r.idx_celda],
                    "dist_celda_km": r.dist_celda_km,
                    "fuente": r.fuente,
                }
                for r in q.itertuples()
            ],
            "sin_celda": [
                {
                    "id": r.id,
                    "nombre": r.nombre,
                    "motivo": f"la celda más cercana está a {r.dist_celda_km:.0f} km",
                }
                for r in fuera.itertuples()
            ],
            "validacion": val,
            "importancia": importancia,
            "mapa": mapa,
            "candidatos": candidatos,
        }

    resultado["excluidos"] = [
        {"id": r.id, "nombre": r.nombre, "verificacion": r.verificacion, "motivo": r.motivo_exclusion}
        for r in positivos[positivos.familia == ""].itertuples()
    ]
    exportar.escribir_json(salida / "candidatos.json", resultado)
    exportar.escribir_json(
        salida / "candidatos.geojson", {"type": "FeatureCollection", "features": geo_features}
    )
    exportar.escribir_json(salida / "leyenda.json", exportar.LEYENDA)
    exportar.registrar_en_manifest(datos, VERSION, list(FAMILIAS))
    print(f"\n✅ Resultados en {salida}")


if __name__ == "__main__":
    main()
