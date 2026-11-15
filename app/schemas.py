"""Modelos de respuesta. El OpenAPI que generan es el contrato con el front."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class Salud(BaseModel):
    estado: str = Field(examples=["ok"])
    version_api: str = Field(examples=["0.1.0"])
    datos_cargados: bool


class CapaResumen(BaseModel):
    id: str = Field(examples=["clima"])
    version: str | None = Field(default=None, examples=["clima_v1"])
    archivo: str | None = Field(default=None, examples=["clima_v1/clima.json"])
    disponible: bool = Field(description="El archivo está en la carpeta de datos")
    extras: dict[str, str] = Field(
        default_factory=dict, description="Otros archivos de la capa (p. ej. sitios)"
    )


class Cuerpo(BaseModel):
    id: str = Field(examples=["luna"])
    version: str | None = None
    nombre: str | None = None


class Meta(BaseModel):
    proyecto: str | None = None
    version_manifest: str | None = None
    generado: str | None = Field(default=None, description="Fecha de generación del manifest")
    version_datos: dict[str, Any] | None = Field(
        default=None, description="Contenido de data/VERSION.json (fecha y hash de la sincronización)"
    )
    cuerpos: list[Cuerpo]
    capas: list[CapaResumen]


CapaSitioId = Literal["topografia", "clima", "geologia", "hielo", "cuevas", "anortosita"]


class Pareja(BaseModel):
    """Lugar o región de la Tierra comparado con un sitio, en el formato común a todas las capas."""

    id: str | None = Field(examples=["lofoten_flakstadoy"])
    nombre: str = Field(examples=["Lofoten (macizo de Flakstadøy), Noruega"])
    lat: float | None = Field(
        default=None, examples=[68.1], description="Latitud del lugar de la Tierra (centro, si es una región)"
    )
    lon: float | None = Field(default=None, examples=[13.25], description="Longitud del lugar de la Tierra")
    distancia: float | None = Field(
        description="Distancia principal de la capa (0 = igual, 1 = nada parecido)"
    )
    parecido: bool | None = Field(
        description="Si la capa la marca como análogo (None si la capa no lo decide por pareja)"
    )
    detalles: dict[str, Any] = Field(description="Resto de campos de la capa (brechas, KS, verificación…)")


class ResumenCapa(BaseModel):
    capa: CapaSitioId
    descripcion: str
    hay_parecido: bool | None = Field(description="Veredicto de la capa para el sitio")
    mejor: Pareja | None = Field(description="Pareja con menor distancia")
    n_parejas: int


class SitioResumen(BaseModel):
    id: str = Field(examples=["artemis-malapert-massif"])
    nombre: str = Field(examples=["Malapert Massif"])
    cuerpo: str = Field(examples=["luna"])
    tipo: str = Field(examples=["region_aterrizaje_artemis"])
    lat: float | None
    lon: float | None
    capas: list[CapaSitioId] = Field(description="Capas con datos para este sitio")
    parecidos: dict[str, bool | None] = Field(description="Veredicto de cada capa (hay análogo o no)")


class SitioDetalle(SitioResumen):
    propiedades: dict[str, Any] = Field(
        description="Propiedades del GeoJSON del sitio (fuente, área, tipo de cueva…)"
    )
    geometria: dict[str, Any] | None = Field(description="Geometría GeoJSON (punto o polígono)")
    resumen: list[ResumenCapa]
    datos_capas: dict[str, dict[str, Any]] = Field(
        description="Registro completo de cada capa para el sitio, sin las listas de parejas"
    )


# --- M1: buscador de análogos nuevos (resultados precalculados en modelos/m1) ---


class Contribucion(BaseModel):
    """Una variable de la explicación SHAP de un candidato."""

    variable: str = Field(examples=["frac_volcanica"])
    valor: float | None = Field(description="Valor de la variable en la mejor celda de la región")
    contribucion: float = Field(description="Valor SHAP en log-odds: > 0 empuja hacia «análogo»")
    sentido: Literal["a favor", "en contra"]


class AnalogoCercano(BaseModel):
    id: str = Field(examples=["golan_jubas"])
    nombre: str
    dist_km: int


class Candidato(BaseModel):
    """Región de la Tierra que M1 propone como análogo (celdas vecinas del 1 % superior)."""

    id: str = Field(examples=["volcanico_basaltico-1"])
    familia: str = Field(examples=["volcanico_basaltico"])
    rango: int = Field(description="Puesto dentro de su familia (1 = mejor)")
    nombre: str = Field(
        examples=["Cerca de Djibouti (Djibouti, DJ)"], description="Población GeoNames más cercana"
    )
    pais_iso: str = Field(examples=["DJ"])
    referencia: dict[str, Any] = Field(description="Población de referencia del nombre y su distancia")
    lat: float = Field(description="Centro de la mejor celda de la región")
    lon: float
    puntuacion: float = Field(description="Puntuación de M1 (0–1). Ordena; no es una probabilidad calibrada")
    percentil: float = Field(description="Percentil de la puntuación en la rejilla de la Tierra")
    n_celdas: int
    area_km2: int
    nuevo: bool = Field(description="No hay ningún análogo conocido de la ficha a menos de 200 km")
    analogo_cercano: AnalogoCercano
    variables: dict[str, float | None] = Field(description="Variables del modelo en la mejor celda")
    explicacion: list[Contribucion] = Field(
        description="Las 4 variables que más pesan (SHAP), de más a menos"
    )


class PositivoM1(BaseModel):
    id: str
    nombre: str
    lat: float
    lon: float
    id_celda: str
    dist_celda_km: float
    fuente: str


class SinCelda(BaseModel):
    id: str
    nombre: str
    motivo: str


class CeldaValidacion(BaseModel):
    analogos: list[str] = Field(description="Análogos de la ficha que caen en esa celda")
    percentil_m1: float = Field(description="Percentil que le da M1 sin haberlo visto en el entrenamiento")
    percentil_indice: float = Field(description="Percentil del índice hecho a mano, como referencia")


class PuntoControl(BaseModel):
    nombre: str
    lat: float
    lon: float
    percentil_m1: float


class ValidacionM1(BaseModel):
    metodo: str
    celdas: list[CeldaValidacion]
    mediana_m1: float
    minimo_m1: float
    top5_m1: float = Field(description="Fracción de análogos dejados fuera que quedan en el 5 % superior")
    top10_m1: float
    mediana_indice: float
    top10_indice: float
    controles: list[PuntoControl] = Field(description="Lugares que no deberían salir altos")
    prueba_ciega: list[PuntoControl] = Field(
        default_factory=list, description="Lugares que el modelo nunca vio y que sí deberían salir altos"
    )


class Importancia(BaseModel):
    variable: str
    media_abs_shap: float = Field(description="Media del |SHAP| en una muestra de 5000 celdas")


class FamiliaM1(BaseModel):
    id: str = Field(examples=["marte_seco"])
    nombre: str
    descripcion: str
    variables: list[str]
    monotonia: dict[str, int] = Field(
        description="+1: la puntuación solo sube con la variable; −1: solo baja"
    )
    positivos: list[PositivoM1]
    sin_celda: list[SinCelda] = Field(description="Análogos de la familia que no caen en la rejilla")
    validacion: ValidacionM1
    importancia: list[Importancia]
    mapa_url: str = Field(examples=["/api/v1/mapas/marte_seco.png"])
    n_candidatos: int


class ExcluidoM1(BaseModel):
    id: str
    nombre: str
    verificacion: str
    motivo: str


class ModeloM1(BaseModel):
    version: str = Field(examples=["m1_v0"])
    generado: str
    modelo: dict[str, Any] = Field(description="Método y parámetros del entrenamiento")
    rejilla: dict[str, Any]
    variables: dict[str, str] = Field(description="Variable → descripción")
    leyenda: dict[str, Any] | None = Field(description="Rampa de color de los mapas PNG (percentil 80–100)")
    png_limites: dict[str, float] | None = Field(description="Límites Web Mercator de los PNG")
    familias: list[FamiliaM1]
    excluidos: list[ExcluidoM1] = Field(description="Análogos de la ficha que M1 no usa, y por qué")


# --- Hielo: pareja con la Tierra (hielo_v0) + comprobación de LRO en el polo sur lunar (hielo_v1.1) ---

NivelHielo = Literal["frío + hidrógeno", "solo frío", "solo hidrógeno", "sin señal"]
Rugosidad = Literal["baja", "media", "alta"]
Veredicto = Literal["se mantiene", "debilitada", "no se sostiene", "sin comprobar"]


class ComprobacionLRO(BaseModel):
    """Dos pruebas independientes de LRO (Diviner y LEND) y la rugosidad de radar (Mini-RF)."""

    nivel: NivelHielo = Field(description="Combinación de las señales de Diviner (frío) y LEND (hidrógeno)")
    diviner_f_hielo: float | None = Field(
        description="Fracción del sitio con hielo estable cerca de la superficie (0–1)"
    )
    senal_diviner: bool = Field(description="diviner_f_hielo ≥ 0,25")
    lend_supresion: float | None = Field(
        description="Supresión de neutrones epitérmicos frente a 55–60° S (sin restar el fondo de la nave)"
    )
    lend_err: float | None = Field(description="Error estadístico de la supresión (ruido de conteo)")
    lend_exceso: float | None = Field(description="Supresión del sitio menos la mediana del polo")
    lend_z_polo: float | None = Field(description="lend_exceso / lend_err")
    lend_percentil: float | None = Field(description="Percentil frente a 2000 discos al azar del polo")
    senal_lend: bool = Field(description="lend_z_polo ≥ 2 y lend_percentil ≥ 75, con un radio de 20 km")
    lend_radios_con_senal: int = Field(description="Radios (15, 20 y 30 km) con señal de LEND, 0–3")
    lend_robusta: bool = Field(description="Hay señal con los tres radios")
    minirf_frac_cpr_gt1: float | None = Field(description="Fracción del sitio con CPR > 1 (banda S)")
    rugosidad_radar_percentil: float | None
    rugosidad_radar: Rugosidad | None = Field(
        description="Bloques a escala de decímetros frente al resto del polo; no es una prueba de hielo"
    )


class RegionHielo(BaseModel):
    """Región de la Tierra comparada con un sitio por hielo y topografía."""

    region_id: str = Field(examples=["analogo-luna-askja-islandia"])
    region: str = Field(examples=["Askja, Islandia"])
    perfil: str | None = Field(description="Perfil del índice de la región (luna o marte)")
    f_permafrost: float | None = Field(description="Probabilidad media de permafrost en la región (0–1)")
    d_hielo: float | None = Field(description="|f_hielo del sitio − f_permafrost de la región|")
    d_topo: float | None = Field(description="Distancia topográfica (KS, 0–1)")
    d_hielo_topo: float | None = Field(description="Media de d_hielo y d_topo (0 = igual)")
    base_cercana: str | None = Field(default=None, description="Estación antártica abierta más cercana")
    base_km: float | None = Field(default=None)


class SitioHielo(BaseModel):
    id: str = Field(examples=["aterrizaje-im-2-athena"])
    nombre: str = Field(examples=["IM-2 Athena"])
    cuerpo: str = Field(examples=["luna"])
    tipo: str
    lat: float | None
    lon: float | None
    f_hielo: float | None = Field(description="Fracción del sitio con hielo cerca de la superficie (0–1)")
    fuente_hielo: str | None = Field(examples=["Diviner PRP (hielo estable)"])
    tiene_analogo: bool | None = Field(
        description="hielo_v0 encuentra una región parecida en hielo y topografía (None: sin comparación)"
    )
    mejor_region: str | None = Field(examples=["Askja, Islandia"])
    d_hielo_topo: float | None
    nivel_lro: NivelHielo | None = Field(description="Solo los 12 sitios lunares por debajo de −80°")


class SitioHieloDetalle(SitioHielo):
    h2o_grs_pct: float | None = Field(
        description="Agua equivalente de Mars Odyssey GRS (% en peso). Solo Marte"
    )
    regiones: list[RegionHielo] = Field(description="Las 5 regiones de la Tierra más parecidas")
    lro: ComprobacionLRO | None = Field(description="Comprobación de LRO (None fuera del polo sur lunar)")


class ParejaHielo(BaseModel):
    """Análogo de hielo: un sitio de la Luna o Marte y su región de la Tierra, con su veredicto."""

    sitio_id: str = Field(examples=["aterrizaje-im-1-odysseus"])
    sitio: str = Field(examples=["IM-1 Odysseus"])
    cuerpo: str = Field(examples=["luna"])
    f_hielo_sitio: float | None
    fuente_hielo: str | None
    region: RegionHielo
    veredicto: Veredicto = Field(
        description="Según la comprobación de LRO; «sin comprobar» si el sitio solo tiene una fuente"
    )
    motivo: str = Field(description="Frase que explica el veredicto, lista para mostrar")
    nivel_lro: NivelHielo | None


class FuenteHielo(BaseModel):
    instrumento: str = Field(examples=["LEND"])
    producto: str
    url: str


class ResumenHielo(BaseModel):
    versiones: dict[str, str | None] = Field(examples=[{"hielo": "hielo_v0", "hielo_lro": "hielo_v1.1"}])
    n_sitios: dict[str, int] = Field(description="Sitios con dato de hielo, por cuerpo")
    n_parejas: dict[str, int] = Field(description="Análogos de hielo, por cuerpo")
    veredictos: dict[str, int] = Field(description="Número de parejas con cada veredicto")
    niveles_lro: dict[str, int] = Field(description="Sitios del polo sur lunar en cada nivel")
    umbrales: dict[str, dict[str, float]] = Field(description="Umbrales de cada versión")
    avisos: list[str] = Field(description="Limitaciones que el front debe mostrar junto a los datos")
    fuentes: list[FuenteHielo]


# --- Usos de misión (enfoque D): capa usos_v0 ---

CapaUsoId = Literal["topografia", "geologia", "clima", "hielo", "forma_cueva"]


class Uso(BaseModel):
    id: str = Field(examples=["aterrizaje"])
    nombre: str = Field(examples=["Aterrizaje y navegación"])
    descripcion: str
    pesos: dict[CapaUsoId, float] = Field(description="Peso de cada capa en la puntuación del uso")
    requiere: list[CapaUsoId] = Field(description="Capas que la pareja tiene que tener medidas")
    solo_sitios: Literal["con_hielo", "cuevas"] | None = Field(
        description="Limita el uso a sitios con hielo (≥ 20 %) o a sitios-cueva"
    )
    orden: Literal["puntuacion", "capas_ok"]
    min_capas_ok: int = Field(description="Capas que tienen que pasar su umbral para que la pareja sea apta")
    n_sitios: int = Field(description="Sitios con al menos una pareja evaluada en este uso")


class Usos(BaseModel):
    version: str | None
    umbrales: dict[CapaUsoId, float] = Field(description="Distancia máxima para que una capa «funcione»")
    usos: list[Uso]
    nota: str | None = None


class ParejaUso(BaseModel):
    """Lugar de la Tierra comparado con un sitio, con lo que funciona y lo que falla en cada capa."""

    tierra_id: str = Field(examples=["lofoten_flakstadoy"])
    tierra_nombre: str = Field(examples=["Lofoten (macizo de Flakstadøy), Noruega"])
    tierra_lat: float | None
    tierra_lon: float | None
    puntuacion: float = Field(description="0–1: media ponderada de similitudes del uso (0,5 = en el umbral)")
    cobertura: float = Field(description="Fracción del peso del uso con dato en esta pareja")
    apta: bool = Field(description="Pasa el umbral en las capas obligatorias del uso")
    n_capas_ok: int = Field(description="Capas del uso que pasan su umbral")
    distancias: dict[CapaUsoId, float] = Field(description="Distancia de cada capa medida (0 = igual)")
    funciona: list[CapaUsoId] = Field(description="Capas que pasan su umbral")
    falla: list[CapaUsoId] = Field(description="Capas medidas que no pasan su umbral")
    sin_dato: list[CapaUsoId] = Field(description="Capas del uso sin medir para esta pareja")
    brechas_C: dict[str, float] = Field(
        description="Sitio − Tierra en °C; negativo = el sitio es más frío (ts_media, ts_min, ts_max, amplitud_anual, osc_diaria, t_interior)"
    )
    fuentes: list[str] = Field(description="Capas que propusieron esta pareja")


class RankingSitio(BaseModel):
    sitio_id: str
    nombre: str
    cuerpo: str
    tipo: str
    lat: float | None
    lon: float | None
    n_aptas: int = Field(description="Parejas aptas para el uso")
    mejor: ParejaUso | None
