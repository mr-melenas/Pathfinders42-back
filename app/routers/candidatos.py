"""M1: lugares nuevos de la Tierra que propone el modelo, su explicación y los mapas de puntuación.

Todo sale de ``data/06_web/m1_v0`` (lo genera ``python -m modelos.m1.entrenar``). Aquí no hay modelo.
"""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import FileResponse

from app.dependencias import DatosDep
from app.m1 import ResultadosM1
from app.schemas import Candidato, FamiliaM1, ModeloM1

router = APIRouter(tags=["candidatos (M1)"])

SIN_M1 = {404: {"description": "M1 no está en los datos, o familia / candidato desconocidos"}}
PREFIJO_MAPAS = "/api/v1/mapas"


def _m1(datos: DatosDep) -> ResultadosM1:
    m1 = datos.m1
    if m1 is None or not m1.disponible:
        raise HTTPException(status_code=404, detail="Los resultados de M1 no están en los datos (capa m1)")
    return m1


def _comprobar_familia(m1: ResultadosM1, familia: str | None) -> None:
    if familia is not None and familia not in m1.familias:
        raise HTTPException(
            status_code=404,
            detail=f"Familia desconocida: {familia}. Familias: {', '.join(m1.familias)}",
        )


@router.get(
    "/candidatos",
    response_model=list[Candidato],
    summary="Lugares nuevos que propone M1, de mejor a peor",
    responses=SIN_M1,
)
def listar(
    datos: DatosDep,
    familia: Annotated[
        str | None, Query(description="marte_seco o volcanico_basaltico (ver /candidatos/modelo)")
    ] = None,
    solo_nuevos: Annotated[
        bool, Query(description="Solo los que no tienen un análogo conocido cerca")
    ] = False,
    n: Annotated[int, Query(ge=1, le=100, description="Número máximo de candidatos")] = 20,
) -> list[dict[str, Any]]:
    m1 = _m1(datos)
    _comprobar_familia(m1, familia)
    salida = [
        c
        for c in m1.candidatos.values()
        if (familia is None or c["familia"] == familia) and (not solo_nuevos or c["nuevo"])
    ]
    # Con familia: su orden (rango). Sin familia: todas mezcladas por percentil
    salida.sort(key=lambda c: (c["rango"],) if familia else (-c["percentil"], c["rango"]))
    return salida[:n]


@router.get(
    "/candidatos/geojson",
    response_model=dict[str, Any],
    summary="Regiones candidatas como FeatureCollection (MultiPolygon de celdas), para el mapa",
    responses=SIN_M1,
)
def geojson(
    datos: DatosDep,
    familia: Annotated[str | None, Query(description="Filtra por familia")] = None,
) -> dict[str, Any]:
    m1 = _m1(datos)
    _comprobar_familia(m1, familia)
    features = [
        f for f in m1.geojson.get("features", []) if familia is None or f["properties"]["familia"] == familia
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get(
    "/candidatos/modelo",
    response_model=ModeloM1,
    summary="Cómo se entrenó M1: familias, positivos, validación, importancia de variables y leyenda",
    responses=SIN_M1,
)
def modelo(datos: DatosDep) -> ModeloM1:
    m1 = _m1(datos)
    r = m1.resultado
    return ModeloM1(
        version=r.get("version", ""),
        generado=r.get("generado", ""),
        modelo=r.get("modelo", {}),
        rejilla=r.get("rejilla", {}),
        variables=r.get("variables", {}),
        leyenda=datos.leer_json(m1.info.get("leyenda")),
        png_limites=datos.manifest.get("png_limites"),
        familias=[
            FamiliaM1(
                **{k: v for k, v in f.items() if k not in {"candidatos", "mapa"}},
                mapa_url=f"{PREFIJO_MAPAS}/{fid}.png",
                n_candidatos=len(f.get("candidatos", [])),
            )
            for fid, f in m1.familias.items()
        ],
        excluidos=r.get("excluidos", []),
    )


@router.get(
    "/candidatos/{candidato_id}",
    response_model=Candidato,
    summary="Un candidato con sus variables y la explicación SHAP",
    responses=SIN_M1,
)
def detalle(candidato_id: str, datos: DatosDep) -> dict[str, Any]:
    c = _m1(datos).candidatos.get(candidato_id)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Candidato desconocido: {candidato_id}")
    return c


@router.get(
    "/mapas/{familia}.png",
    summary="Mapa de puntuación de M1 (PNG Web Mercator, mismos límites que los índices)",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}, **SIN_M1},
)
def mapa(datos: DatosDep, familia: Annotated[str, Path(description="Familia de M1")]) -> FileResponse:
    m1 = _m1(datos)
    _comprobar_familia(m1, familia)
    ruta = m1.ruta_mapa(familia)
    if ruta is None:
        raise HTTPException(status_code=404, detail=f"El mapa de {familia} no está sincronizado")
    return FileResponse(ruta, media_type="image/png")
