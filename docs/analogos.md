# Fichas de análogos · capa `analogos_v0`

**En una frase:** para cada pareja sitio de la Luna o Marte ↔ lugar de la Tierra, una ficha con los **pros**
(dónde funciona la analogía), los **contras** (dónde falla), las capas **sin medir** y los **límites de la
Tierra** como análogo, en español y en inglés.

## De dónde sale cada punto
| Punto | Origen |
|---|---|
| Pro / contra de capa | La capa `usos_v0`, que une todas las capas: la capa pasa (pro) o no (contra) su umbral. Lleva distancia, umbral y datos (sitio · Tierra) |
| Contra de temperatura | Las brechas en °C (sitio − Tierra). Es un contra si la media difiere 10 °C o más, **aunque la capa clima pase**: clima compara posiciones relativas (percentiles), no grados |
| Verificación | La ficha de análogos (Google Sheet `ficha_analogos`, copia en `scripts/entrada/`). Verificada = pro con su referencia; candidato o pendiente = contra; región de los índices sin fuente = «hipótesis» (contra) |
| Usos aptos | Usos de misión en los que la pareja es apta (pro) |
| Sin dato | Capas sin medir para esa pareja |
| Límites de la Tierra | Una vez por cuerpo: gravedad, atmósfera o vacío y radiación, con su fuente (NASA NSSDC, Hassler et al. 2014, Zhang et al. 2020) |

Sin LLM: todo sale de los datos. El LLM solo lo explica cuando se le pregunta (`POST /preguntar` con
`sitio_id` y `tierra_id`): recibe la ficha y la regla de no añadir otras capas; si se inventa una cifra, se usa
la plantilla («A favor… En contra… Límites de la Tierra…»).

## API
| Método y ruta | Devuelve |
|---|---|
| `GET /api/v1/analogos/{sitio_id}?n=&solo_aptos=&verificacion=` | Análogos del sitio con su frase y nº de pros y contras (aptos primero) |
| `GET /api/v1/analogos/{sitio_id}/{tierra_id}` | Ficha completa: pros, contras, sin dato, límites de la Tierra |
| `POST /api/v1/preguntar` con `tierra_id` | El asistente explica ese análogo |

## Regenerar
`python scripts/construir_analogos.py` (después de `construir_usos.py`). `sync_data.py` ejecuta los dos.
