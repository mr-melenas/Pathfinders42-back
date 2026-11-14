"""Aprendizaje PU (positivos + sin etiquetar) con bagging y LightGBM.

Problema: tenemos unos pocos análogos verificados (positivos) y ~39 000 celdas de las que no sabemos
nada (sin etiquetar). No hay negativos de verdad: que nadie haya estudiado un lugar no quiere decir que
no sea análogo.

Método (Mordelet y Vert, 2014, «A bagging SVM to learn from positive and unlabeled examples»):
1. En cada ronda («bolsa») se toma una muestra al azar de las celdas sin etiquetar y se tratan como
   negativos provisionales.
2. Se entrena un clasificador positivos vs esa muestra.
3. Cada celda se puntúa solo con los modelos de las bolsas en las que NO estuvo (fuera de bolsa, OOB):
   así la puntuación de una celda nunca sale de un modelo que la vio como «negativa».
4. La media de muchas bolsas reduce el ruido de haber tomado por negativos a algunos positivos ocultos.

La salida es una puntuación 0–1 que ordena las celdas, no una probabilidad calibrada: sin saber qué
fracción de la Tierra es análoga (la «prior» de clase), no se puede calibrar.
"""

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np

# Árboles muy pequeños y regularizados: con ~10 positivos, un modelo grande los memoriza.
PARAMS_LGBM: dict = {
    "n_estimators": 150,
    "learning_rate": 0.05,
    "num_leaves": 7,
    "max_depth": 3,
    "min_child_samples": 3,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "verbose": -1,
}


@dataclass
class ResultadoPU:
    puntuacion: np.ndarray  # media fuera de bolsa por celda (NaN si la celda nunca quedó fuera)
    modelos: list = field(repr=False)


def entrenar_pu(
    X: np.ndarray,
    positivos: np.ndarray,
    excluir_de_negativos: np.ndarray | None = None,
    n_bolsas: int = 100,
    ratio: int = 10,
    semilla: int = 42,
    params: dict | None = None,
) -> ResultadoPU:
    """Bagging PU.

    X: matriz celdas x variables (NaN permitido: LightGBM los trata).
    positivos: índices de las filas positivas.
    excluir_de_negativos: máscara booleana de celdas que nunca se usan como negativos provisionales
        (la zona de amortiguación alrededor de los positivos: coordenadas aproximadas y celdas vecinas).
    ratio: negativos provisionales por positivo en cada bolsa (se compensa con scale_pos_weight).
    """
    rng = np.random.default_rng(semilla)
    n = len(X)
    es_pos = np.zeros(n, dtype=bool)
    es_pos[positivos] = True
    vetadas = es_pos if excluir_de_negativos is None else es_pos | excluir_de_negativos
    pool = np.flatnonzero(~vetadas)
    k = min(len(pool), ratio * len(positivos))
    suma = np.zeros(n)
    veces = np.zeros(n)
    modelos = []
    cfg = {**PARAMS_LGBM, **(params or {})}
    for b in range(n_bolsas):
        negs = rng.choice(pool, size=k, replace=False)
        idx = np.concatenate([positivos, negs])
        y = np.concatenate([np.ones(len(positivos)), np.zeros(k)])
        modelo = lgb.LGBMClassifier(**cfg, scale_pos_weight=k / len(positivos), random_state=semilla + b)
        modelo.fit(X[idx], y)
        fuera = np.ones(n, dtype=bool)
        fuera[idx] = False
        suma[fuera] += modelo.predict_proba(X[fuera])[:, 1]
        veces[fuera] += 1
        modelos.append(modelo)
    with np.errstate(invalid="ignore"):
        puntuacion = suma / veces
    return ResultadoPU(puntuacion=puntuacion, modelos=modelos)


def predecir(modelos: list, X: np.ndarray) -> np.ndarray:
    """Media de todas las bolsas (para celdas que no estuvieron en ninguna, como los positivos)."""
    return np.mean([m.predict_proba(X)[:, 1] for m in modelos], axis=0)


def percentil(puntuacion: np.ndarray, valores: np.ndarray | None = None) -> np.ndarray:
    """Percentil (0–100) de cada valor dentro de la distribución de puntuaciones de la rejilla.

    Con empates se usa el rango medio: con árboles pequeños muchas celdas comparten la puntuación
    mínima, y contar solo «menores o iguales» las pondría a todas en un percentil alto.
    """
    ref = np.sort(puntuacion[~np.isnan(puntuacion)])
    valores = puntuacion if valores is None else valores
    menores = np.searchsorted(ref, valores, side="left")
    iguales = np.searchsorted(ref, valores, side="right") - menores
    return 100.0 * (menores + 0.5 * iguales) / len(ref)
