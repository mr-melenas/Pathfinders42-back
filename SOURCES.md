# Fuentes de datos y licencias

El código de este repositorio es MIT (ver `LICENSE`). Los datos que sirve la API se calculan en los
notebooks de Colab del equipo a partir de datos abiertos; cada fuente conserva su licencia.

La bibliografía completa, con citas y enlaces, está en el documento del equipo «Bibliografía y fuentes de
datos — Análogos terrestres Luna y Marte» (Drive, carpeta `01_docs`). **Este archivo se actualiza cada vez
que una capa nueva usa una fuente nueva.**

La columna «Recurso del reto» indica qué recurso de la lista oficial del desafío (pestaña *Resources*)
cubre cada fuente. «—» significa que es otra fuente abierta.

## Sitios de la Luna y Marte

| Datos | Fuente | Recurso del reto | Licencia / condiciones |
|---|---|---|---|
| 9 regiones candidatas Artemis III (polígonos) | USGS ScienceBase, *Down Selected Artemis III Candidate Landing Site Navigational Grids* | — | Dominio público (USGS) |
| 47 zonas de exploración humana de Marte | OpenPlanetary (Exploration Zones) | — | Según el repositorio |
| Aterrizajes tripulados, robóticos y planificados | Coordenadas publicadas por cada misión | — | Datos factuales |

## Capas por sitio

| Capa | Cuerpo | Fuente | Recurso del reto | Licencia / condiciones |
|---|---|---|---|---|
| Topografía | Tierra | Copernicus DEM GLO-30 (ESA, 2021; bucket público `copernicus-dem-30m`) | Copernicus Data Space Ecosystem (ESA) | Licencia Copernicus DEM: uso libre con atribución |
| Topografía | Luna | LRO LOLA | NASA PDS / LRO | Dominio público (NASA) |
| Topografía | Marte | MGS MOLA | NASA PDS | Dominio público (NASA) |
| Clima | Tierra | MODIS Aqua MYD11C3 v061, temperatura de la superficie (NASA LP DAAC) | NASA Earthdata | Datos abiertos NASA |
| Clima | Tierra | MERRA-2 (NASA GMAO), incluido M2SMNXSLV | NASA Earthdata | Datos abiertos NASA |
| Clima | Luna | LRO Diviner GCP (curvas diurnas) y PRP (recursos polares) | LRO Diviner | Dominio público (NASA) |
| Clima | Marte | MACDA v2.0 (Mars Analysis Correction Data Assimilation), vía ARCO-Mars | — | Datos abiertos con cita |
| Geología | Tierra | GLiM, *Global Lithological Map* (Hartmann y Moosdorf, 2012) | — | CC BY (cita requerida) |
| Geología | Luna | USGS *Unified Geologic Map of the Moon* 1:5M | — | Dominio público (USGS) |
| Geología | Marte | USGS SIM 3292, mapa geológico global de Marte | — | Dominio público (USGS) |
| Química | Luna | Lunar Prospector GRS (FeO, TiO₂, Th) | NASA PDS | Dominio público (NASA) |
| Química | Marte | Mars Odyssey GRS (Fe, Si, Cl, H₂O, K, Th) | NASA PDS | Dominio público (NASA) |
| Cloruros | Marte | Osterloo et al. (2010); Leask y Ehlmann (2021) | — | Cita requerida |
| Hielo | Luna | LRO Diviner PRP (hielo estable bajo la superficie) | LRO Diviner | Dominio público (NASA) |
| Hielo | Marte | SWIM, *Subsurface Water Ice Mapping* (PSI, NASA/JPL) | — | Datos abiertos con cita |
| Permafrost | Tierra | Obu et al. (2019), probabilidad de permafrost a 1 km (PANGAEA) | — | CC BY (cita requerida) |
| Bases antárticas | Tierra | COMNAP, instalaciones antárticas | — | Según sus condiciones de uso |
| Cuevas | Luna | LROC *Lunar Pit Atlas* (Wagner y Robinson, 2021; ASU / NASA) | LRO | Datos abiertos con cita |
| Cuevas | Marte | *Mars Global Cave Candidate Catalog* (MGC³, Cushing; USGS) | — | Dominio público (USGS) |
| Cuevas | Tierra | Pyroduct Digital Catalog (Zenodo), USGS HVO y literatura citada en la ficha | — | Según cada registro |
| Anortosita | Tierra | Ficha de análogos (ESA, CSA, NASA JSC y otras fuentes citadas) | — | Según cada fuente |

## Modelo M1 (buscador de análogos nuevos)

| Datos | Fuente | Recurso del reto | Licencia / condiciones |
|---|---|---|---|
| Rejilla y clima (temperatura, precipitación, elevación) | MERRA-2 2014–2023 (NASA GMAO) | NASA Earthdata | Datos abiertos NASA |
| Vegetación (NDVI) | VIIRS VNP13C2 v002 | NASA Earthdata | Datos abiertos NASA |
| Emisividad térmica | CAMEL (a través del índice lunar `luna_v0.3`) | NASA Earthdata | Datos abiertos NASA |
| Roca volcánica | GLiM (a través del índice lunar `luna_v0.3`) | — | CC BY (cita requerida) |
| Nombres de lugar | GeoNames (a través de `reverse_geocoder`) | — | CC BY 4.0 |

## En preparación

| Capa | Fuente | Recurso del reto | Estado |
|---|---|---|---|
| Hielo lunar v1 | LRO Mini-RF, mosaico global de CPR a 32 px/grado (`LRO-L-MRFLRO-5-GLOBAL-MOSAIC-V1.0`) | LRO (PDS Geosciences) | Notebook `hielo_v1` |
| Hielo lunar v1 | LRO LEND, datos promediados ALD del polo sur (`LRO-L-LEND-4/5-RDR-V1.0`) | LRO (PDS Geosciences) | Notebook `hielo_v1` |

## Recursos del reto que todavía no usamos

- **NASA Worldview / GIBS**: imagen de satélite de cada análogo de la Tierra en el mapa del front.
- **RADARSAT-1 y RADARSAT Constellation Mission (CSA)**: radar de apertura sintética; comparación de
  rugosidad con Mini-RF. Fuera de alcance para este fin de semana.
- **JAXA G-Portal** y **ESA Open Science Catalog**: sin uso previsto por ahora.

Antes de la entrega hay que revisar esta tabla contra la bibliografía (tarea «Citas y licencias en la
entrega» del GitHub Project).
