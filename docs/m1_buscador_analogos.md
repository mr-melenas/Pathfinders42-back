# M1 · Buscador de análogos nuevos (m1_v0)

> **En una frase:** M1 aprende cómo son, según los datos de satélite, los análogos que ya conocemos de la Luna y
> Marte, y recorre la Tierra celda a celda (~50 km) buscando lugares que se les parezcan y que nadie ha
> propuesto todavía. Es la «herramienta de IA/ML para encontrar análogos no reconocidos» que pide el reto.

Fecha: 10 nov 2026 · Código: `modelos/m1/` · Datos: `data/06_web/m1_v0/` · API: `/api/v1/candidatos`, `/api/v1/mapas`

---

## 1. Resumen de resultados

| | Marte seco | Basalto desnudo |
|---|---|---|
| Qué busca | Desiertos polares, de altura e hiperáridos | Coladas y campos de basalto poco cubiertos de vegetación |
| Análogos de la ficha usados (celdas) | 6 (5 zonas) | 12 (9 celdas, 6 zonas) |
| **Validación: mediana del percentil de los análogos escondidos** | **96,4** (índice hecho a mano: 87,9) | **96,1** (índice hecho a mano: 84,4) |
| Análogos escondidos en el 10 % superior | 83 % (índice: 50 %) | 67 % (índice: 44 %) |
| Prueba ciega (6 campos volcánicos que el modelo nunca vio) | — | **95–99,9** (todos en el 5 % superior) |
| Regiones candidatas | 12, de ellas **9 nuevas** | 20, de ellas **18 nuevas** |
| Variable que más pesa (SHAP) | temperatura del mes cálido, NDVI | NDVI, suelo desnudo, roca volcánica |

**Conclusiones principales**

1. Con muy pocos ejemplos (6 y 9 celdas), un modelo pequeño y bien restringido recupera los análogos que le
   escondemos mejor que nuestros índices hechos a mano. M1 no sustituye a los índices: los complementa.
2. M1 **vuelve a encontrar por su cuenta** tres de los seis campos volcánicos de la prueba ciega: caen
   dentro de sus regiones candidatas (Payún Matrú → candidato 8, Harrat Khaybar → 4, Al Haruj → 13; el Hoggar
   queda a ~110 km del 17). Además propone provincias de basalto conocidas por la geología que no están en
   nuestra ficha: Afar (Yibuti), Turkana, Harrat ash-Shamah o el Tibesti.
3. La lección más importante del proceso: **el modelo aprende los sesgos de sus positivos**. La primera
   versión subía «montañas húmedas con algo de vegetación» porque Hawái e Islandia son así a 50 km. Lo
   arreglamos con conocimiento del dominio (restricciones monótonas y elección de variables), no con más datos
   (apartado 7).
4. Los candidatos son **hipótesis**, no análogos verificados. Antes de presentarlos como análogos hay que
   buscar fuentes, igual que con la ficha.

---

## 2. El problema: ¿por qué «aprendizaje PU»?

Un clasificador normal necesita ejemplos de las dos clases: lugares que **son** análogos y lugares que **no**
lo son. Nosotros tenemos:

- **Positivos (P):** ~30 análogos verificados en la ficha, cada uno con una fuente que lo presenta como análogo.
- **Sin etiquetar (U, de *unlabeled*):** las ~39 500 celdas restantes de la Tierra.

No tenemos **negativos de verdad**. Que nadie haya estudiado un lugar no significa que no sea análogo: es
justo lo que queremos descubrir. Si tratáramos todas las celdas sin etiquetar como negativas, castigaríamos al
modelo precisamente por encontrar análogos nuevos.

Este escenario se llama **aprendizaje PU** (*Positive-Unlabeled learning*), y es muy habitual en ciencia: genes
asociados a una enfermedad, especies en un mapa de distribución, fraudes confirmados entre millones de
transacciones…

### La solución que usamos: bagging PU (Mordelet y Vert, 2014)

1. En cada ronda («bolsa») tomamos **una muestra al azar** de celdas sin etiquetar (10 por cada positivo) y
   las tratamos como **negativos provisionales**.
2. Entrenamos un clasificador LightGBM: positivos frente a esa muestra.
3. Cada celda se puntúa **solo con los modelos de las bolsas en las que no estuvo** (*out-of-bag*, OOB). Así,
   la puntuación de una celda nunca sale de un modelo que la usó como «negativa».
4. Repetimos 100 veces y hacemos la media. Si en una bolsa cayó por azar un análogo oculto entre los
   negativos, en las otras 99 no: el ruido se diluye.

Además, en una **zona de amortiguación** de 150 km alrededor de cada positivo no tomamos negativos
provisionales. Las coordenadas de la ficha son aproximadas y las celdas vecinas de un análogo suelen ser
análogas también: no queremos enseñar al modelo que «justo al lado de Atacama no es Atacama».

**La salida es una puntuación de 0 a 1 que ordena, no una probabilidad.** Para convertirla en probabilidad
haría falta saber qué fracción de la Tierra es análoga (la *prior* de clase), y no lo sabemos. Por eso la API
da la `puntuacion` y su `percentil` en la rejilla («esta celda está en el 1 % más parecido»).

---

## 3. Datos

### 3.1 La rejilla

Usamos la rejilla de `v1.3/celdas.parquet` (índice de Marte): **39 507 celdas de tierra sin hielo** de
0,5° × 0,625° (~50 km, la rejilla del reanálisis MERRA-2), entre 55° S y 84° N.

⚠ **Lo que no está en la rejilla:** la Antártida (está fuera del dominio) y las islas pequeñas (MERRA-2 no las
ve como tierra a 50 km). Por eso **McMurdo, University Valley, Lanzarote y La Corona no pueden ser
positivos**, aunque estén verificados. Lo exporta la API en `sin_celda`.

### 3.2 Variables (12)

| Variable | Qué mide | De dónde sale |
|---|---|---|
| `T_media`, `T_frio`, `T_calido` | Temperatura media anual, del mes más frío y del más cálido (°C) | MERRA-2 2014–2023 |
| `amplitud_termica` | `T_calido − T_frio` | calculada |
| `P_anual` | Precipitación anual (mm) | MERRA-2 |
| `elevacion` | Elevación media de la celda (m) | MERRA-2 |
| `rugosidad` | Desviación típica de la elevación con las 8 celdas vecinas: relieve a ~150 km | calculada |
| `ndvi_max` | NDVI máximo: cuánta vegetación hay | VIIRS VNP13C2 2023 |
| `frac_desnudo` | Fracción de suelo desnudo (NDVI < 0,15) | VIIRS |
| `emis_p_max` | Percentil máximo del índice de emisividad térmica lunar dentro de la celda | `luna_v0.3/celdas.parquet` (0,05°) |
| `frac_emis_p90` | Fracción de la celda con índice de emisividad ≥ p90 | idem |
| `frac_volcanica` | Fracción de la celda con ≥ 50 % de roca volcánica (GLiM) en suelo desnudo | idem |

Las tres últimas se **agregan** desde las celdas finas de 0,05° del índice lunar (125 celdas finas por cada
celda gruesa). Donde no hay celdas finas (vegetación, nieve, o percentil < 50) valen 0.

**Variables que no usamos a propósito:**
- El **percentil del índice de Marte**: sería enseñar al modelo a copiar el índice hecho a mano (*fuga* o
  circularidad).
- **Latitud y longitud**: el modelo aprendería «cerca de un análogo conocido» en vez de «se parece a uno».
- `presion_aprox`: es una función directa de la elevación (información repetida).

### 3.3 Positivos y familias

Un solo modelo para «todo lo que es análogo» mezclaría cosas sin relación (un desierto polar y un tubo de
lava no se parecen en nada). Por eso M1 entrena **un modelo por familia**, y solo en las familias que las
variables de la rejilla pueden «ver»:

| Familia | Positivos (de la ficha, verificados) |
|---|---|
| `marte_seco` | Qaidam, Axel Heiberg, Devon, Atacama, Tso Kar, Cordillera de la Sal (+ McMurdo y University Valley, sin celda) |
| `volcanico_basaltico` | Mauna Kea, Kīlauea, pozos del Kīlauea, tubos del Mauna Loa, Craters of the Moon, Pinacate, Lava Beds, Askja, Krafla, Lofthellir, Surtshellir, Golán (+ Lanzarote y La Corona, sin celda) |

**Excluidos y por qué** (están en `modelos/m1/positivos.csv` y en la API, en `excluidos`):
- **Anortosita** (Lofoten, Mistastin, Stillwater, Shawmere, White Mountain, Egersund): la rejilla no tiene
  ninguna variable que distinga la anortosita. Un modelo con estos positivos aprendería «sitio frío del norte»,
  que no es lo que los hace análogos. Ya los cubre la capa `anortosita_v0`.
- **Meteor Crater**: no hay ninguna variable de impacto.
- **Río Tinto**: su analogía es química (aguas ácidas, hierro), y la rejilla no mide química.
- **Candidatos y pendientes** (Lop Nur, Undara, Erebus): no tienen una fuente que los llame análogos. Undara se
  usa como prueba ciega.

`positivos.csv` es una **instantánea** de la ficha (Google Sheet «ficha_analogos», pestaña Fichas, 10 nov).
Se versiona para que el entrenamiento sea reproducible. Si la ficha cambia, hay que actualizarla y reentrenar.

---

## 4. El modelo: LightGBM pequeño y restringido

**LightGBM** es una implementación de *gradient boosting* con árboles de decisión: suma muchos árboles
pequeños, y cada uno corrige los errores de los anteriores. Es la opción por defecto para datos tabulares,
entrena en segundos en CPU, acepta valores vacíos (NaN) y funciona bien con SHAP.

Con tan pocos positivos, el riesgo es el **sobreajuste**: que el modelo memorice los 6 o 9 ejemplos en vez de
aprender una regla general. Por eso:

| Parámetro | Valor | Por qué |
|---|---|---|
| `num_leaves` / `max_depth` | 7 / 3 | árboles muy simples (como mucho 3 preguntas seguidas) |
| `n_estimators`, `learning_rate` | 150, 0,05 | pasos pequeños |
| `min_child_samples` | 3 | una hoja necesita al menos 3 ejemplos (tiene que ser menor que el número de positivos) |
| `subsample`, `colsample_bytree` | 0,8 | cada árbol ve el 80 % de las filas y de las variables: más diversidad |
| `reg_lambda` | 1 | regularización L2 |
| `scale_pos_weight` | 10 | compensa los 10 negativos provisionales por positivo |
| **`monotone_constraints`** | por familia | ver abajo |

**Nada de redes profundas:** con ~10 positivos, una red memorizaría. Más datos de entrenamiento no existen:
el límite son los análogos verificados.

### Restricciones monótonas: conocimiento del dominio dentro del modelo

LightGBM permite obligar a que la puntuación **solo suba** (+1) o **solo baje** (−1) cuando aumenta una variable.
Es una forma de decirle al modelo lo que ya sabemos de física:

- `marte_seco`: más lluvia (−1) o más vegetación (−1) nunca hace un lugar más «marciano»; más suelo desnudo (+1) sí.
- `volcanico_basaltico`: más roca volcánica (+1), más emisividad de basalto (+1) y más suelo desnudo (+1) suben;
  más vegetación (−1) baja.

Las temperaturas se dejan libres: Atacama (cálido) y Devon (frío) son análogos los dos.

---

## 5. Explicación con SHAP

**SHAP** (*SHapley Additive exPlanations*, Lundberg y Lee, 2017) reparte la puntuación de cada celda entre sus
variables, usando los valores de Shapley de la teoría de juegos: cuánto aporta cada variable en promedio
frente a no tenerla. Para árboles se calcula de forma exacta y rápida (*TreeSHAP*).

- **Por candidato** (`explicacion`): las 4 variables que más pesan, con su valor y su contribución. Ejemplo,
  candidato 1 basáltico (Yibuti): `frac_volcanica = 0,34 → +3,12`, `ndvi_max = 0,16 → +1,41`,
  `frac_desnudo = 0,35 → +1,02`. Se lee: «es candidato sobre todo porque un tercio de la celda es basalto
  desnudo y casi no tiene vegetación».
- **Global** (`importancia`): media del |SHAP| en 5000 celdas al azar.

Las contribuciones están en **log-odds** (la escala interna del modelo, antes de convertirla en 0–1): lo que
importa es el signo y el tamaño relativo, no el número exacto. M1 usa la media de 25 de las 100 bolsas.

| Marte seco | |SHAP| medio | Basalto desnudo | |SHAP| medio |
|---|---|---|---|
| `T_calido` | 1,10 | `ndvi_max` | 1,41 |
| `ndvi_max` | 0,97 | `frac_desnudo` | 0,57 |
| `P_anual` | 0,43 | `frac_volcanica` | 0,53 |
| `frac_desnudo` | 0,28 | `emis_p_max` | 0,06 |
| `rugosidad` | 0,18 | `frac_emis_p90` | 0,004 |

**Lectura:** el «Marte seco» es, para el modelo, «veranos fríos o suaves + sin vegetación + sin lluvia». En
basalto, la emisividad apenas pesa porque ya está metida en `frac_volcanica`, que solo cuenta las celdas del
dominio del índice lunar (suelo desnudo y percentil ≥ 50): las variables comparten información.

---

## 6. Validación: ¿cómo sabemos que funciona?

No hay negativos, así que la métrica clásica (precisión, AUC) no sirve. Usamos cuatro pruebas:

### 6.1 Dejar fuera cada grupo de análogos (*leave-one-group-out*)

Escondemos un análogo, entrenamos con los demás y miramos **en qué percentil de toda la Tierra** queda el que
escondimos. Si queda arriba, el modelo generaliza; si no, solo memorizaba. Los análogos a menos de 300 km
(los cuatro de Hawái, los cuatro de Islandia) se esconden juntos: si no, el vecino «chivaría» la respuesta
(**fuga espacial**).

Comparamos con el índice hecho a mano en las mismas celdas (`percentil_indice`).

| Análogo escondido | M1 | Índice | | Análogo escondido | M1 | Índice |
|---|---|---|---|---|---|---|
| Atacama | 91,1 | 98,0 | | Tubos del Mauna Loa | 97,7 | 84,4 |
| Cordillera de la Sal | 96,1 | 82,2 | | Kīlauea + pozos | 75,0 | 81,0 |
| Tso Kar | 96,7 | 82,3 | | Mauna Kea | 96,1 | 82,7 |
| Qaidam | 99,0 | 90,8 | | Pinacate | 99,3 | 95,9 |
| Devon | 80,1 | 85,0 | | Golán | 96,1 | 96,4 |
| Axel Heiberg | 99,5 | 96,5 | | Lava Beds | 56,0 | 38,8 |
| | | | | Craters of the Moon | 73,9 | 38,8 |
| | | | | Surtshellir | 98,6 | 98,9 |
| | | | | Askja, Krafla, Lofthellir | 99,9 | 99,5 |
| **Mediana** | **96,4** | 87,9 | | **Mediana** | **96,1** | 84,4 |

Para el índice de Marte, el percentil es «dentro de su perfil», no en toda la rejilla: la comparación es
orientativa.

**Dónde falla:** Lava Beds y Craters of the Moon. A 50 km, sus celdas están cubiertas de vegetación (estepa y
bosque) y el basalto ocupa poco: el análogo es puntual y la rejilla es gruesa. Es un límite de la escala, no
del método.

### 6.2 Prueba ciega

Seis campos volcánicos que **no están entre los positivos** (son los de prueba de `luna_v0.3`) y Undara
(candidato sin fuente):

| Lugar | Percentil M1 |
|---|---|
| Al Haruj (Libia) | 99,8 |
| Harrat Khaybar (Arabia Saudí) | 99,9 |
| Harrat Rahat (Arabia Saudí) | 96,0 |
| Hoggar – Atakor (Argelia) | 99,0 |
| Payún Matrú (Argentina) | 99,9 |
| Holuhraun (Islandia) | 99,7 |
| Tubos de Undara (Australia) | 51,5 |

Undara sale bajo porque está en una sabana con vegetación: igual que Lava Beds, es un análogo de forma
(tubo de lava), no de superficie.

### 6.3 Controles negativos

| Control | Marte seco | Basalto |
|---|---|---|
| Amazonía central | 36,2 | 53,1 |
| Cuenca del Congo | 12,8 | 21,0 |
| Delta del Ganges | 26,8 | 57,6 |
| París | 48,8 | 48,5 |
| Borneo | 37,0 | 21,0 |
| Pampa húmeda | 3,3 | 21,0 |
| Taiga de Siberia | 60,6 | 21,0 |
| Gran Erg Occidental (arena) | 85,8 | 80,4 |

Ninguno llega al 5 % superior. Dos matices:
- En basalto, casi toda la Tierra tiene `frac_volcanica = 0`: **por debajo del ~p60 el modelo no distingue**
  (muchas celdas empatan). Por eso el mapa solo pinta del p80 hacia arriba.
- El mar de arena sale alto en Marte seco. No es un error: es seco y desnudo, y Marte también tiene dunas. La
  rejilla no mide la textura del suelo (arena frente a roca), y ese es uno de sus límites.

### 6.4 Comprobación a ojo

Los mapas (`mapa_<familia>.png`) pintan donde se espera: el Ártico canadiense, los Andes áridos, el Sáhara,
Arabia, el Tíbet y el Pamir en Marte seco; los harrats de Arabia, Islandia, el Afar y los Andes volcánicos en
basalto.

---

## 7. Lo que salió mal y cómo se corrigió (la parte más útil para aprender)

### Iteraciones 0 y 1: demasiadas variables en la familia basáltica

- **Iteración 0** (experimento con las 12 variables en las dos familias): Borneo salía en el p75 de basalto y el
  Delta del Ganges en el p66. El clima tropical húmedo de Hawái se colaba como «rasgo de análogo».
- **Iteración 1** (sin clima, pero con relieve y elevación): validación muy buena (mediana de 98,6). **Pero el
  SHAP enseñaba que el modelo casi no usaba la emisividad** (|SHAP| de 0,03): lo que más pesaba era la
  rugosidad (1,27) y el NDVI (0,82), con su punto dulce en ~0,5. Los mejores candidatos eran montañas con
  vegetación: Arusha (junto al Kilimanjaro), Samburu (Kenia), Kamchatka, Armenia, Columbia Británica.

**Causa: sesgo de los positivos.** Hawái, Islandia y el Golán son montañosos y tienen algo de vegetación a
escala de 50 km. El modelo aprendió lo que tienen en común *sus ejemplos*, no lo que hace análogo a un lugar.
La métrica de validación no lo detectaba, porque los análogos escondidos comparten el mismo sesgo.

> **Lección:** una buena métrica de validación no basta. Con pocos positivos hay que mirar *por qué* decide el
> modelo (SHAP) y *qué* propone (los candidatos), y preguntarse si tiene sentido físico.

### Iteración 2: conocimiento del dominio

- Para basalto, **solo variables de roca y superficie**: fuera el clima y el relieve.
- **Restricciones monótonas** (apartado 4).
- Resultado: la validación baja un poco (mediana de 98,6 → 96,1; Lava Beds de 76 a 56), pero los candidatos pasan
  a ser provincias de basalto reales (Afar, harrats de Arabia, Tibesti, Haruj), y la prueba ciega mejora en
  conjunto (Al Haruj 97,4 → 99,8; Hoggar 95,0 → 99,0; Harrat Khaybar 99,4 → 99,9; Harrat Rahat baja de 97,6
  a 96,0).

### Otros dos errores corregidos

- **Candidatos amontonados:** 15 de los 20 candidatos de Marte seco estaban en el Ártico canadiense, junto a
  Devon y Axel Heiberg. Ahora se exige una **separación mínima de 500 km** entre candidatos (como la *non-maximum
  suppression* de los detectores de objetos).
- **Percentil con empates:** con árboles pequeños muchas celdas tienen exactamente la misma puntuación. Contar
  «cuántas son menores o iguales» subía a todas las empatadas (la Amazonía salía en el 53). Ahora se usa el
  **rango medio** (hay un test que lo comprueba).

---

## 8. Candidatos

Región candidata = celdas vecinas del **1 % superior**; se exporta la mejor celda. «Nuevo» = no hay ningún
análogo de la ficha a menos de 200 km. El nombre es la población más cercana según GeoNames (paquete
`reverse_geocoder`, sin red); **la provincia que da GeoNames a veces está mal** (p. ej., «Hebei» en el
Tíbet): hay que comprobarla antes de usarla en el pitch.

### Marte seco (12)

| # | Lugar | lat, lon | Percentil | Nuevo |
|---|---|---|---|---|
| 1 | A 100 km de Rutog (Tíbet occidental, China) | 34,0, 78,75 | 100 | no (Tso Kar, 104 km) |
| 2 | Isla de Ellesmere / Axel Heiberg (Nunavut, Canadá) | 79,0, −88,75 | 100 | no (Axel Heiberg, 61 km) |
| 3 | Cerca de Calama (Antofagasta, Chile) | −22,5, −68,75 | 99,99 | no (Cordillera de la Sal, 68 km) |
| 4 | Isla de Baffin, a 160 km de Clyde River (Canadá) | 71,0, −72,5 | 99,85 | **sí** |
| 5 | Pamir, a 90 km de Karakenja (Tayikistán) | 39,0, 72,5 | 99,84 | **sí** |
| 6 | Cerca de La Capilla (Moquegua, Perú) | −17,0, −71,25 | 99,56 | **sí** |
| 7 | Cuenca del Tarim, a 70 km de Tumxuk (Xinjiang, China) | 42,0, 80,0 | 99,54 | **sí** |
| 8 | Changtang (Tíbet, China) | 34,5, 85,63 | 99,53 | **sí** |
| 9 | Andes centrales, a 60 km de Los Andes (Chile) | −33,0, −70,0 | 99,51 | **sí** |
| 10 | Archipiélago ártico, a 600 km de Gjoa Haven (Canadá) | 73,0, −86,25 | 99,21 | **sí** |
| 11 | Gobi, cerca de Dzalaa (Bayanhongor, Mongolia) | 44,5, 99,38 | 99,20 | **sí** |
| 12 | Oeste de Groenlandia, a 160 km de Uummannaq | 72,0, −53,75 | 99,16 | **sí** |

Que los tres primeros sean zonas ya conocidas (no «nuevas») es buena señal: el modelo reencuentra lo conocido
antes de proponer lo nuevo.

### Basalto desnudo (los 10 primeros de 20)

| # | Lugar | lat, lon | Percentil | Nuevo |
|---|---|---|---|---|
| 1 | Afar, cerca de Yibuti | 11,5, 43,13 | 100 | **sí** |
| 2 | Turkana, a 140 km de Lodwar (Kenia) | 3,0, 36,88 | 100 | **sí** |
| 3 | Harrat ash-Shamah, a 60 km de Malah (Siria) | 32,5, 37,5 | 99,99 | no (Golán, 181 km) |
| 4 | Harrat de Arabia, a 170 km de Sultanah (Arabia Saudí): incluye Harrat Khaybar | 26,0, 39,38 | 99,99 | **sí** |
| 5 | Cerca de Kushkak (Farah, Afganistán) | 32,5, 61,25 | 99,95 | **sí** |
| 6 | Cerca de Jajarm (Jorasán del Norte, Irán) | 36,5, 56,25 | 99,93 | **sí** |
| 7 | Altiplano, a 150 km de Colchani (Potosí, Bolivia) | −21,0, −68,13 | 99,93 | **sí** |
| 8 | Payenia, a 60 km de Barrancas (Neuquén, Argentina): incluye Payún Matrú | −36,5, −69,38 | 99,91 | **sí** |
| 9 | A 110 km de Calvinia (Cabo Septentrional, Sudáfrica) | −30,5, 19,38 | 99,90 | **sí** |
| 10 | Cerca de Rabor (Kermán, Irán) | 29,5, 56,88 | 99,90 | **sí** |

Del 11 al 20: sur de Islandia, Jizán (Arabia Saudí), Al Haruj (Libia, incluye el campo de la prueba ciega),
Santa Cruz (Patagonia), Tibesti (Chad), Kassala (Sudán), cerca de Tamanrasset (Hoggar, Argelia), Tabriz (Irán),
Kunene (Namibia) y Vallenar (Chile).

En basalto, la puntuación está **saturada** en lo más alto (0,968–0,971): el orden dentro del top 20 es casi
un empate y no hay que darle importancia. Lo que vale es estar en la lista.

**Siguiente paso con los candidatos:** buscar fuentes que los presenten como análogos (como se hizo con la
ficha). El Afar es un buen ejemplo: Dallol, que está en el Afar, ya figura en la ficha como candidato sin
coordenadas.

---

## 9. Límites (lo que M1 no puede decir)

- **Escala de 50 km.** Describe la región, no el punto. Un tubo de lava concreto o un cráter no se ven.
- **Solo ve lo que miden las variables:** clima, vegetación, relieve grueso y basalto desnudo. No ve
  anortosita, impactos, química, hielo en el subsuelo ni la textura del suelo.
- **Pocos positivos** (6 y 9 celdas): los resultados dependen de qué análogos hay en la ficha. Un análogo
  nuevo verificado puede cambiar los candidatos.
- **Puntuación, no probabilidad.**
- **Sin Antártida ni islas pequeñas.**
- **La Tierra como análogo** tiene los límites de siempre: gravedad, atmósfera, vacío y radiación. M1 compara la
  superficie, no esas condiciones.

---

## 10. API (v0.3.0)

| Método y ruta | Devuelve |
|---|---|
| `GET /api/v1/candidatos?familia=&solo_nuevos=&n=` | Candidatos (con familia: por rango; sin familia: todos por percentil) |
| `GET /api/v1/candidatos/geojson?familia=` | Regiones como FeatureCollection (MultiPolygon de celdas) |
| `GET /api/v1/candidatos/modelo` | Familias, positivos, validación, importancia, variables, leyenda y límites de los PNG |
| `GET /api/v1/candidatos/{id}` | Un candidato (`marte_seco-5`, `volcanico_basaltico-1`…) |
| `GET /api/v1/mapas/{familia}.png` | Mapa de percentil (Web Mercator, ±85,05°, igual que los índices) |

Cambio respecto al plan: el parámetro es **`familia`**, no `uso`. Con los positivos que hay, no se puede
entrenar un modelo por uso de misión (aterrizaje, ISRU…). Cada familia se puede asociar a varios usos en el
front (enfoque D).

Para el front: el mapa se pone como en los índices (MapLibre, fuente `image`, coordenadas de `png_limites`),
con la `leyenda` de `/candidatos/modelo` (percentil 80–100). En la ficha del candidato, mostrar `explicacion`
como barras a favor y en contra, y avisar de que `nuevo` quiere decir «sin análogo conocido cerca», no
«verificado».

---

## 11. Cómo reentrenar

```bash
pip install -e ".[ml]"                   # pandas, pyarrow, lightgbm, shap, pillow, reverse_geocoder
python -m modelos.m1.entrenar            # ~40 s en CPU; escribe data/06_web/m1_v0 y la capa m1 del manifest
pytest                                   # tests/test_m1_pu.py solo corre si lightgbm está instalado
```

En Colab: `python -m modelos.m1.entrenar --datos "/content/drive/MyDrive/Hackathon Nasa/06_web"`.

⚠ **Drive es la fuente de `06_web`:** `scripts/sync_data.py` borra `data/06_web` y lo copia desde Drive. Antes de
la próxima sincronización hay que **subir `m1_v0/` a `06_web` de Drive y añadir la capa `m1` a su
`manifest.json`** (o ejecutar el script en Colab contra Drive). Si no, la sincronización borra M1.

Archivos:

```
modelos/m1/
  positivos.csv   instantánea de la ficha con la familia de cada análogo (o el motivo de exclusión)
  rejilla.py      tabla celda × variables y asignación de positivos a celdas
  pu.py           bagging PU con LightGBM y percentil con empates
  exportar.py     regiones candidatas, SHAP, nombres, PNG, GeoJSON y manifest
  entrenar.py     configuración de las familias, validación y exportación (punto de entrada)
```

---

## 12. Glosario

- **Aprendizaje supervisado:** aprender una regla a partir de ejemplos con su respuesta (etiqueta).
- **Aprendizaje PU (*Positive-Unlabeled*):** caso en el que solo hay ejemplos positivos y ejemplos sin etiquetar;
  no hay negativos confirmados.
- **Negativo provisional:** celda sin etiquetar que, en una bolsa concreta, se trata como negativa.
- **Bagging (*bootstrap aggregating*):** entrenar muchos modelos con muestras distintas y promediarlos; reduce
  la varianza.
- **Bolsa:** cada una de esas rondas de entrenamiento.
- **OOB (*out-of-bag*, fuera de bolsa):** puntuar cada ejemplo solo con los modelos que no lo vieron.
- **Prior de clase:** proporción real de positivos en la población. Sin ella, no se puede calibrar una probabilidad.
- **Calibración:** que una puntuación de 0,8 signifique de verdad un 80 % de casos positivos. M1 no está calibrado.
- **Gradient boosting / LightGBM:** suma de árboles pequeños, cada uno corrigiendo los errores de los anteriores.
- **Hoja (*leaf*):** final de un árbol de decisión, donde se da la predicción.
- **Sobreajuste (*overfitting*):** memorizar los ejemplos en vez de aprender una regla general.
- **Regularización:** cualquier freno a la complejidad del modelo (árboles pequeños, L2, submuestreo).
- **Restricción monótona:** obligar a que la predicción solo suba (o solo baje) con una variable.
- **Variable (*feature*):** cada columna que usa el modelo.
- **Fuga de información (*leakage*):** que el modelo vea, directa o indirectamente, la respuesta; por ejemplo,
  usar el índice que queremos mejorar como variable, o validar con una celda vecina de una de entrenamiento.
- **Fuga espacial:** validar con un lugar que está pegado a uno de entrenamiento. Se evita agrupando por distancia.
- **Leave-one-group-out:** validación en la que se deja fuera un grupo entero (aquí, una zona) cada vez.
- **Zona de amortiguación (*buffer*):** franja alrededor de los positivos de donde no se toman negativos.
- **Prueba ciega:** evaluar con casos que el modelo no vio y que nosotros sabemos que deberían salir altos.
- **Control negativo:** caso que no debería salir alto.
- **Línea base (*baseline*):** método sencillo con el que compararse; aquí, los índices hechos a mano.
- **Percentil:** posición en la distribución de 0 a 100 (p99 = mejor que el 99 % de las celdas).
- **Rango medio:** manera de dar percentil a valores empatados (la media de sus posiciones).
- **SHAP / valor de Shapley:** reparto de una predicción entre las variables según su aportación media.
- **Log-odds:** logaritmo de p/(1−p), la escala interna del clasificador antes de pasarla a 0–1.
- **Non-maximum suppression:** quedarse con el mejor de un grupo de candidatos cercanos y descartar el resto.
- **Sesgo de los positivos:** el modelo aprende lo que comparten los ejemplos aunque no sea lo que importa.
- **Web Mercator (EPSG:3857):** la proyección de los mapas web; por eso los PNG llegan hasta ±85,05°.

---

## 13. Siguientes pasos (si sobra tiempo)

1. Buscar fuentes para los candidatos nuevos más fuertes (Afar, Turkana, Pamir, Changtang, Payenia) y, si las
   hay, pasarlos a la ficha como verificados y reentrenar.
2. Añadir variables con las que M1 vería más cosas: pendiente y relieve de Copernicus a 240 m en la rejilla,
   permafrost y nieve (ya se usan en las capas por sitio).
3. Unir familias y usos en el front (enfoque D): p. ej., «pruebas de movilidad» → Marte seco, «cuevas y
   refugio» → basalto desnudo.
4. Probar con más semillas, para medir cuánto cambian los candidatos (estabilidad).

## Referencias

- Mordelet, F. y Vert, J.-P. (2014). A bagging SVM to learn from positive and unlabeled examples. *Pattern
  Recognition Letters*, 37, 201–209.
- Elkan, C. y Noto, K. (2008). Learning classifiers from only positive and unlabeled data. *KDD 2008*.
- Bekker, J. y Davis, J. (2020). Learning from positive and unlabeled data: a survey. *Machine Learning*, 109, 719–760.
- Ke, G. et al. (2017). LightGBM: A highly efficient gradient boosting decision tree. *NeurIPS 2017*.
- Lundberg, S. y Lee, S.-I. (2017). A unified approach to interpreting model predictions. *NeurIPS 2017*.
- Hartmann, J. y Moosdorf, N. (2012). The new global lithological map database GLiM. *G-Cubed*, 13, Q12004.
- Datos: MERRA-2 (NASA GMAO), VIIRS VNP13C2 v002, índice lunar `luna_v0.3` (emisividad + GLiM), GeoNames
  (a través de `reverse_geocoder`).
