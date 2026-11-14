# Pathfinders42 · API

Backend del proyecto del **NASA Space Apps Challenge 2026**: análogos terrestres de las bases y lugares
de aterrizaje de la Luna y Marte. La API sirve resultados **precalculados** en Colab (topografía, clima,
geología, hielo, cuevas y anortosita); no entrena ni ejecuta modelos pesados.

## Origen del código

Este repositorio arranca el 14/11/2026, primer día del hackathon. La base inicial (esqueleto de la API,
endpoints de capas, sitios y candidatos de M1, módulo de explicaciones y datos de `data/06_web`) se trajo
del repo de preparación [Pathfinders42](https://github.com/mr-melenas/Pathfinders42) (rama `dev`, commit
`86d60a4`), donde está su historial completo. Los notebooks de Colab y los datos de Drive no se tocan.
Todo lo que se hace desde aquí entra por ramas `feat/…` o `fix/…` con PR a `dev`.

## Arrancar en local

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
python scripts/sync_data.py --origen "/ruta/a/Hackathon Nasa/06_web"   # copia los datos a data/06_web
uvicorn app.main:app --reload
```

Documentación interactiva en <http://localhost:8000/docs>. El contrato para el front es
<http://localhost:8000/openapi.json>.

Sin datos sincronizados la API arranca igual: `/api/v1/health` responde con `datos_cargados: false`
y el resto de endpoints devuelve 503.

## Endpoints (v0.3)

| Método y ruta | Qué devuelve |
|---|---|
| `GET /api/v1/health` | Estado de la API y si hay datos cargados |
| `GET /api/v1/meta` | Versión del manifest y de la sincronización, cuerpos y capas disponibles |
| `GET /api/v1/capas` | Capas registradas en el manifest y si su archivo está sincronizado |
| `GET /api/v1/capas/{capa}` | Archivo completo de una capa (JSON o GeoJSON) |
| `GET /api/v1/sitios?cuerpo=&tipo=&capa=` | Sitios de la Luna y Marte (160, incluidos los sitios-cueva) con el veredicto de cada capa |
| `GET /api/v1/sitios/geojson` | Los mismos sitios como FeatureCollection, para el mapa |
| `GET /api/v1/sitios/{id}` | Ficha del sitio: propiedades, geometría, mejor pareja de cada capa y datos de cada capa |
| `GET /api/v1/sitios/{id}/parejas?capa=&n=` | Parejas de la Tierra en una capa (topografia, clima, geologia, hielo, cuevas, anortosita), primero las marcadas como análogo |
| `GET /api/v1/candidatos?familia=&solo_nuevos=&n=` | Lugares nuevos que propone el modelo M1, con su explicación SHAP |
| `GET /api/v1/candidatos/geojson?familia=` | Regiones candidatas de M1 como FeatureCollection |
| `GET /api/v1/candidatos/modelo` | Cómo se entrenó M1: familias, positivos, validación, importancia de variables, leyenda |
| `GET /api/v1/candidatos/{id}` | Un candidato de M1 |
| `GET /api/v1/mapas/{familia}.png` | Mapa de puntuación de M1 (Web Mercator, como los índices) |
| `GET /api/v1/hielo` | Resumen de hielo: análogos por cuerpo, veredictos, niveles de LRO, umbrales, avisos y fuentes |
| `GET /api/v1/hielo/sitios?cuerpo=&solo_analogos=` | Hielo de cada sitio de la Luna y Marte y su mejor región de la Tierra |
| `GET /api/v1/hielo/sitios/{id}` | Ficha de hielo: 5 regiones de la Tierra y, en el polo sur lunar, la comprobación de LRO (Diviner, LEND, Mini-RF) |
| `GET /api/v1/hielo/parejas?cuerpo=&veredicto=` | Análogos de hielo con su veredicto (se mantiene, debilitada, no se sostiene, sin comprobar) y una frase que lo explica |

Los siguientes (análogos, usos, ranking y asistente) están en el plan de desarrollo y en el GitHub Project.

## Modelo M1 (buscador de análogos nuevos)

Aprendizaje PU con bagging y LightGBM sobre la rejilla de la Tierra, explicado con SHAP. Se entrena fuera
del servidor y la API solo sirve su salida (`data/06_web/m1_v0`):

```bash
pip install -e ".[ml]"
python -m modelos.m1.entrenar        # ~40 s en CPU
```

Método, validación, resultados, límites y glosario: [`docs/m1_buscador_analogos.md`](docs/m1_buscador_analogos.md).

## Ramas y flujo de trabajo

```
feat/… ──PR──▶ dev ──PR (release)──▶ main
fix/…  ──PR──▶ dev
```

- **`main`**: lo que está desplegado y se enseña en la entrega. Solo recibe PR desde `dev`.
- **`dev`**: integración. Todas las ramas de trabajo salen de `dev` y vuelven a `dev` por PR.
- Cuando `dev` está probado (CI en verde y comprobado en el despliegue de prueba), se abre un PR
  `dev → main` y se aprueba.
- Las correcciones urgentes también pasan por `dev`; nadie hace push directo a `main` ni a `dev`.

```bash
git checkout dev && git pull
git checkout -b feat/mi-tarea
# … cambios, commits …
git push -u origin feat/mi-tarea   # y abrir el PR con base dev
```

## Desarrollo

```bash
pytest                              # tests
ruff check . && ruff format .       # lint y formato
docker build -t pathfinders42-api . && docker run -p 8000:8000 pathfinders42-api
```

- Ramas `feat/…` y `fix/…`; PR pequeño con una revisión y CI en verde.
- Estructura: `app/` (API), `app/routers/` (un archivo por grupo de endpoints), `scripts/` (sincronización
  de datos), `modelos/` (entrenamiento offline de M1; no va en la imagen Docker), `docs/`, `tests/` (con datos
  de prueba en `tests/fixtures/06_web`).

## Datos y licencias

Ver [`SOURCES.md`](SOURCES.md) y [`data/README.md`](data/README.md). Código bajo licencia MIT.
