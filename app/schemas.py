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
