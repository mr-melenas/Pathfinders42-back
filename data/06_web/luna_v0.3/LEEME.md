# Datos para la web · Luna · versión luna_v0.3

- **Capa raster**: `indice_luna.png` (Web Mercator, mismos límites que Marte), percentil 50–100; resto transparente.
- **Regiones**: `regiones.geojson`, 20 candidatas volcánicas con `litologia_glim`, `glim_volcanica`, `area_km2`,
  `analogo_conocido` y `fuente`.
- **Análogos**: `analogos.geojson`, análogos lunares con fuente (`tipo` analogo_luna / impacto) y campos volcánicos de prueba,
  con su percentil y la clase GLiM de su celda.
- **Back**: `celdas.parquet` (lat, lon, percentil, glim_volcanica_pct, region_id), rejilla de 0.05°.
- Las celdas son de ~5 km: describen el entorno, no un punto exacto.
