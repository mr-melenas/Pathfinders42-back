"""Lógica de aprendizaje PU de M1 (solo si están instaladas las dependencias de [ml])."""

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("lightgbm")
from modelos.m1 import pu  # noqa: E402


def test_percentil_con_empates():
    s = np.array([0.1, 0.1, 0.1, 0.1, 0.9])
    p = pu.percentil(s)
    assert p[0] == pytest.approx(40.0)  # rango medio de los 4 empatados, no 80
    assert p[-1] == pytest.approx(90.0)


def test_pu_encuentra_positivos_ocultos():
    """Datos sintéticos: los «análogos» viven en una esquina del espacio de variables."""
    rng = np.random.default_rng(0)
    X = rng.normal(size=(3000, 3))
    ocultos = np.flatnonzero((X[:, 0] > 1.5) & (X[:, 1] > 1.0))
    assert len(ocultos) > 15
    conocidos, escondidos = ocultos[:10], ocultos[10:]
    res = pu.entrenar_pu(X, conocidos, n_bolsas=15, ratio=10, semilla=1)
    s = res.puntuacion.copy()
    s[conocidos] = np.nan
    # Los positivos que el modelo no conocía quedan muy arriba
    assert np.median(pu.percentil(s, s[escondidos])) > 90


def test_restricciones_monotonas():
    rng = np.random.default_rng(1)
    X = rng.uniform(size=(2000, 1))
    positivos = np.flatnonzero(X[:, 0] > 0.9)[:20]
    res = pu.entrenar_pu(X, positivos, n_bolsas=5, params={"monotone_constraints": [1]})
    rejilla = np.linspace(0, 1, 50).reshape(-1, 1)
    pred = pu.predecir(res.modelos, rejilla)
    assert np.all(np.diff(pred) >= -1e-9)  # nunca baja al subir la variable
