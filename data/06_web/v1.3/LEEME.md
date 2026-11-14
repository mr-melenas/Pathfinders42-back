# Datos para la web · versión v1.3

Punto de entrada: `06_web/manifest.json` (siempre apunta a la versión activa).

## Front
- **Capas raster**: `indice_<perfil>.png` (y `indice_todos.png`), en Web Mercator. Límites:
  sur-oeste (-85.0511, -180), norte-este (85.0511, 180).
  - Leaflet: `L.imageOverlay(url, [[-85.0511, -180], [85.0511, 180]])`
  - MapLibre: fuente `image` con `coordinates: [[-180, 85.0511], [180, 85.0511], [180, -85.0511], [-180, -85.0511]]`
- **Leyenda**: `leyenda.json` (paradas de color del percentil 50 al 100).
- **Regiones**: `regiones.geojson`, polígonos con `perfil`, `rango`, `region`, `percentil_max`, `area_km2`, clima,
  `analogo_conocido` (Sí / Pendiente / No) y enlaces `fuente`.
- **Análogos**: `analogos.geojson`, puntos con los datos de la ficha (literatura) y los de satélite (`sat_*`).

## Back
- `celdas.parquet`: una fila por celda de tierra (lat, lon, perfil, percentil, variables climáticas, region_id).
  Para "¿qué valor tiene este punto?", buscar la celda más cercana (rejilla 0.5° x 0.625°).

## Avisos
- Los valores son de celdas de ~50 km (NDVI ~5 km): describen la región, no un punto exacto.
- Las regiones que cruzan el meridiano 180° aparecen separadas.
