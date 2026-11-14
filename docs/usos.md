# Usos de misión (enfoque D) · capa `usos_v0`

**En una frase:** para cada sitio de la Luna o Marte, ordena sus análogos de la Tierra según para qué se
quieran (aterrizar, mover un rover, excavar, probar equipos en frío, buscar hielo, refugiarse en una cueva),
y dice en cada pareja qué capa funciona, cuál falla y cuál no se ha medido.

## Por qué hace falta
Cada capa (`topografia_sitios_v2`, `clima_v1`, `geologia_v0`, `hielo_v0`, `cuevas_v2`, `anortosita_v0`)
guarda solo sus mejores parejas, y las listas casi no coinciden: de mediana, un sitio tiene 11 regiones
distintas entre capas y solo 1 está a la vez en topografía, clima y geología. Sin unirlas, una puntuación
«por uso» dependería de qué capa metió cada pareja en su top, no de los pesos.

## Cómo se construye (`scripts/construir_usos.py`)
1. **Unión** de las parejas de todas las capas (el mismo método que la base de análogos v0).
2. **Relleno** de lo que se puede calcular sin Colab:
   - geología = 1 − fracción de roca compartida, con la composición GLiM de cada región
     (`scripts/entrada/geologia_tierra_glim.csv`). Coincide con geologia_v0 en 480/485 parejas (±0,003);
   - hielo = |f_hielo del sitio − f_permafrost de la región|, solo si el sitio tiene ≥ 20 % de hielo.
   - Topografía, clima y forma de cueva **solo donde alguna capa ya los midió**. No se inventan: lo que
     falta sale en `sin_dato`.
3. **Puntuación por uso** (`scripts/usos.json`, editable): similitud de cada capa
   `s = 1 − d / (2 · umbral)` (1 igual, 0,5 en el umbral, 0 al doble), media ponderada con los pesos del uso.
   - `requiere`: capas que la pareja tiene que tener medidas para entrar en el uso.
   - `apta`: pasa el umbral en todas las capas obligatorias (y, en «general», al menos 2 capas).
   - `cobertura`: qué parte del peso del uso tiene dato.

| Uso | Pesos | Obligatoria | Sitios |
|---|---|---|---|
| General | todas = 1 (ordena por nº de capas que pasan) | — | 160 |
| Aterrizaje y navegación | topo 3, geo 1 | topo | 160 |
| Movilidad de rovers | topo 2, geo 2 | topo, geo | 97 |
| Construcción e ISRU | geo 3, topo 1 | geo | 97 |
| Pruebas térmicas | clima 3, topo 1 | clima | 97 |
| Agua, hielo y permafrost | hielo 3, topo 1, clima 1 | hielo; solo sitios con hielo | 35 |
| Cuevas y hábitat | forma 2, topo 2 | topo; solo sitios-cueva | 63 |

Umbrales: topografía 0,2 · geología 0,4 · clima 0,2 · hielo 0,25 · forma de cueva 0,3.

## Comprobaciones
- «General» da 76 sitios con pareja apta (36 Luna, 40 Marte), lo mismo que la base de análogos v0
  (Alta + Media).
- Aterrizaje en Artemis: las mesetas polares salen con White Mountain y los macizos con Lofoten, como en
  anortosita_v0. Construcción/ISRU en Malapert: White Mountain primero (misma roca, d_geo = 0).

## Límites
- **Clima solo en su top 5**: «pruebas térmicas» solo ve esas parejas. En la Luna el clima discrimina poco
  (clima_v1); las brechas en °C dicen cuánto falla.
- Sin química: no hay uso de astrobiología (sales, aguas ácidas) hasta tener una capa que lo mida.
- Los pesos son una decisión del equipo, no un resultado: están en un archivo para poder discutirlos.

## API
| Método y ruta | Devuelve |
|---|---|
| `GET /api/v1/usos` | usos, pesos, umbrales y nº de sitios de cada uso |
| `GET /api/v1/usos/{uso}/sitios/{sitio_id}?n=&solo_aptas=` | parejas del sitio para el uso, de mejor a peor |
| `GET /api/v1/usos/{uso}/ranking?cuerpo=&tipo=&n=` | mejor pareja de cada sitio (aptas primero) |

Un sitio fuera del alcance del uso (p. ej. Apollo 11 en «agua, hielo») devuelve una lista vacía.

## Regenerar
```bash
python scripts/construir_usos.py                            # datos reales
python scripts/construir_usos.py --web tests/fixtures/06_web  # fixtures de los tests
```
`scripts/sync_data.py` borra `data/06_web` y lo copia de Drive (donde no está `usos_v0`); por eso, al terminar,
vuelve a ejecutar `construir_usos.py` con los datos recién copiados. Para saltarlo: `--sin-usos`.
