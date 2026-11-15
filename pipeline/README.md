# Pipeline de datos: de dónde sale cada dato

Esta carpeta es una copia de la carpeta de trabajo del equipo en Google Drive («Hackathon Nasa»), donde se
descargaron y procesaron en Google Colab los datos de satélite de la Tierra, la Luna y Marte. Sirve para
que cualquiera pueda seguir el camino completo:

```
fuente pública (NASA Earthdata, PDS, USGS, ESA…)
  → notebook de Colab (pipeline/notebooks/)
  → resultados y registro de la ejecución (pipeline/resultados/<versión>/)
  → archivo para la web (data/06_web/<capa>/, registrado en data/06_web/manifest.json)
  → endpoint de la API (/api/v1/…)
```

La API no ejecuta nada de esto: solo sirve los archivos precalculados de `data/06_web`
(ver `CLAUDE.md`). Las fuentes, sus licencias y cómo se descargan están en `SOURCES.md` y en
`pipeline/docs/Bibliografía y fuentes de datos — Análogos terrestres Luna y Marte.docx`.

## Contenido

| Carpeta | Qué hay | En Drive |
|---|---|---|
| `notebooks/` | Notebooks de la versión activa de cada capa, con sus salidas y conclusiones | `02_notebooks` |
| `notebooks/archivo/` | Versiones anteriores de los notebooks y algunos resultados antiguos | `99_archivo` |
| `resultados/` | Una carpeta por versión: tablas CSV, figuras y `registro_*.json` con los datos, umbrales y métricas de esa ejecución | `04_resultados` |
| `analogos/` | Ficha de análogos exportada y base de análogos v0 (con su script `construir_base_analogos.py`) | `05_analogos` |
| `docs/` | Bibliografía (`.docx`) y ficha de análogos (`ficha_analogos.xlsx`): cada análogo «verificado» tiene la fuente que lo presenta como tal | `01_docs` |

**No incluido:** `03_datos` (unos 2 GB). Son las descargas originales (`brutos`), sus derivados
(`procesados`) y las respuestas guardadas de los servicios web (`cache_api`). Todo sale de fuentes públicas y
los notebooks lo vuelven a descargar si falta. Tampoco se copia `06_web`, porque ya está en `data/06_web`
(lo sincroniza `scripts/sync_data.py`). De `resultados/v1.1` y `v1.2` se omiten los `.nc`, que son
iguales en tamaño al de `v1.3`.

## Qué notebook genera cada capa

| Notebook | Qué hace | Resultados | Capa en `data/06_web` (manifest) |
|---|---|---|---|
| `EDA_analogos_v1.3.ipynb` | Índice de Marte: perfiles polar, de altura y árido (MERRA-2, VIIRS) | `resultados/v1.3/` | `regiones`, `analogos`, `celdas` (perfil Marte) |
| `EDA_luna_v0.3.ipynb` | Índice lunar: basalto desnudo con emisividad CAMEL, validado con GLiM | `resultados/luna_v0.3/` | perfil Luna (`luna_v0.3/`) |
| `sitios_objetivo_v0.ipynb` | Regiones Artemis, Exploration Zones de Marte y aterrizajes | `resultados/sitios_v0/` | `sitios` |
| `topografia_v2.ipynb` | Pendiente y relieve de las regiones de la Tierra (Copernicus GLO-30) | `resultados/topografia_v2/` | `topografia` |
| `topografia_sitios_v2.ipynb` | Topografía de los sitios (LOLA, HRSC–MOLA) y comparación con la Tierra | `resultados/topografia_sitios_v2/` | `topografia_sitios` |
| `clima_v1.ipynb` | Temperatura de la superficie: MODIS (Tierra), Diviner (Luna), MACDA (Marte) | `resultados/clima_v1/` | `clima` |
| `geologia_v0.ipynb` | Mapas geológicos de USGS y química GRS frente a GLiM | `resultados/geologia_v0/` | `geologia` |
| `hielo_v0.ipynb` | Diviner PRP, SWIM y permafrost de la Tierra (Obu et al.) | `resultados/hielo_v0/` | `hielo` |
| `hielo_v1.ipynb`, `hielo_v1.1.ipynb` | Hielo del polo sur con Diviner, LEND y Mini-RF | `resultados/hielo_v1/`, `resultados/hielo_v1.1/` | `hielo_lro` |
| `capa_cuevas_v0.ipynb` | Entradas de cueva de OpenStreetMap en las regiones candidatas | `resultados/cuevas_v0/` | `cuevas` |
| `notebooks/archivo/cuevas_v1.ipynb` | Pozos lunares (LROC) y candidatos a cueva de Marte (MGC³) | `resultados/cuevas_v1/` | `cuevas_sitios` |
| `cuevas_v2.ipynb` | Las cuevas como sitios: tipo, forma, terreno y temperatura interior | `resultados/cuevas_v2/` | `cuevas_v2` |
| `anortosita_v0.ipynb` | Afloramientos de anortosita de la Tierra frente a las tierras altas lunares | `resultados/anortosita_v0/` | `anortosita` |
| `exportacion_web.ipynb` | Exporta índices, regiones y análogos a `06_web` y escribe el manifest | — | varias |

Las capas que se construyen en este repo y no en Colab:

| Capa | Script | Documentación |
|---|---|---|
| `m1` (candidatos de M1) | `python -m modelos.m1.entrenar` | `docs/m1_buscador_analogos.md` |
| `usos` | `scripts/construir_usos.py` | `docs/usos.md` |
| `analogos` | `scripts/construir_analogos.py` | `docs/analogos.md` |

## Orden de ejecución

1. `EDA_analogos_v1.3` y `EDA_luna_v0.3` (índices y regiones candidatas de la Tierra).
2. `sitios_objetivo_v0` y `exportacion_web`.
3. `topografia_v2` → `topografia_sitios_v2` → `clima_v1` → `geologia_v0` → `hielo_v0`.
4. `cuevas_v2` → `topografia_sitios_v2` (con `INCLUIR_CUEVAS = True`) → `cuevas_v2` otra vez.
5. `anortosita_v0`, `hielo_v1`, `hielo_v1.1`.
6. En este repo: `scripts/sync_data.py`, M1, `construir_usos.py` y `construir_analogos.py`.

## Cómo reproducir

- Los notebooks están pensados para Google Colab con Google Drive montado en
  `/content/drive/MyDrive/Hackathon Nasa/`, con la misma estructura de carpetas que aquí
  (`02_notebooks`, `03_datos`, `04_resultados`, `06_web`).
- Los productos de NASA Earthdata se descargan con `earthaccess` y una cuenta gratuita de Earthdata. Las
  credenciales van en los secretos de Colab (`EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`), nunca en el código.
- El resto de fuentes (PDS, USGS, PANGAEA, AWS, Hugging Face) son de acceso libre y sin cuenta.
- Cada ejecución deja un `registro_*.json` en `resultados/<versión>/` con los datos, umbrales y métricas
  usados: es la forma de comprobar que un resultado de la web corresponde a una ejecución concreta.
