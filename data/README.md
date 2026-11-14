# data/

Resultados precalculados que sirve la API. **Se versionan en el repo**: cada commit lleva sus datos.

- `06_web/`: copia de las capas actuales de la carpeta `06_web` de Drive (solo lo que referencia
  `manifest.json`; las versiones antiguas se quedan en Drive). El punto de entrada es `manifest.json`.
- `VERSION.json`: fecha, hash y tamaño de la última sincronización (lo escribe el script).

## Cómo actualizar

1. En Colab, genera `06_web_sync.zip` con la celda de sincronización (ver `scripts/sync_data.py`) o usa
   la carpeta de Drive para escritorio.
2. Desde una rama `feat/datos-…` que salga de `dev`:

   ```bash
   python scripts/sync_data.py --origen "/ruta/a/06_web"
   pytest            # tests/test_datos_reales.py comprueba que todas las capas del manifest existen y se leen
   ```

3. PR a `dev` indicando qué capas cambian.

## Normas

- Sincronizar solo cuando una capa está cerrada y en la congelación (12 nov), no tras cada ejecución.
  Git guarda todas las versiones de los archivos binarios: cada sincronización hace crecer el repo.
- Ningún archivo de más de 50 MB (el script avisa).
