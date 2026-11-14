from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app.dependencias import DatosDep
from app.schemas import CapaSitioId, Pareja, SitioDetalle, SitioResumen
from app.sitios import CAPAS, IndiceSitios, Sitio

router = APIRouter(prefix="/sitios", tags=["sitios"])

NO_ENCONTRADO = {404: {"description": "Sitio desconocido o sin datos en esa capa"}}


def _resumen(indice: IndiceSitios, s: Sitio) -> SitioResumen:
    return SitioResumen(
        id=s.id,
        nombre=s.nombre,
        cuerpo=s.cuerpo,
        tipo=s.tipo,
        lat=s.lat,
        lon=s.lon,
        capas=list(s.capas),
        parecidos={c: CAPAS[c].parecido_sitio(r) for c, r in s.capas.items()},
    )


def _buscar(indice: IndiceSitios, sitio_id: str) -> Sitio:
    sitio = indice.sitios.get(sitio_id)
    if sitio is None:
        raise HTTPException(status_code=404, detail=f"Sitio desconocido: {sitio_id}")
    return sitio


@router.get(
    "", response_model=list[SitioResumen], summary="Sitios de la Luna y Marte (incluidos los sitios-cueva)"
)
def listar(
    datos: DatosDep,
    cuerpo: Annotated[str | None, Query(description="luna o marte")] = None,
    tipo: Annotated[str | None, Query(description="p. ej. region_aterrizaje_artemis, cueva_luna")] = None,
    capa: Annotated[CapaSitioId | None, Query(description="Solo sitios con datos en esta capa")] = None,
) -> list[SitioResumen]:
    indice = datos.sitios
    return [
        _resumen(indice, s)
        for s in indice.sitios.values()
        if (cuerpo is None or s.cuerpo == cuerpo)
        and (tipo is None or s.tipo == tipo)
        and (capa is None or capa in s.capas)
    ]


@router.get(
    "/geojson",
    response_model=dict[str, Any],
    summary="Todos los sitios como un FeatureCollection (para pintarlos en el mapa)",
)
def geojson(datos: DatosDep) -> dict[str, Any]:
    indice = datos.sitios
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": s.geometria, "properties": _resumen(indice, s).model_dump()}
            for s in indice.sitios.values()
        ],
    }


@router.get(
    "/{sitio_id}",
    response_model=SitioDetalle,
    summary="Ficha del sitio con el veredicto de cada capa",
    responses=NO_ENCONTRADO,
)
def detalle(sitio_id: str, datos: DatosDep) -> SitioDetalle:
    indice = datos.sitios
    s = _buscar(indice, sitio_id)
    return SitioDetalle(
        **_resumen(indice, s).model_dump(),
        propiedades=s.propiedades,
        geometria=s.geometria,
        resumen=indice.resumen(s),
        datos_capas={c: {k: v for k, v in r.items() if k != CAPAS[c].lista} for c, r in s.capas.items()},
    )


@router.get(
    "/{sitio_id}/parejas",
    response_model=list[Pareja],
    summary="Parejas de la Tierra de un sitio en una capa, de más a menos parecida",
    responses=NO_ENCONTRADO,
)
def parejas(
    sitio_id: str,
    datos: DatosDep,
    capa: Annotated[CapaSitioId, Query(description="Capa de la comparación")] = "topografia",
    n: Annotated[int, Query(ge=1, le=50, description="Número máximo de parejas")] = 10,
) -> list[Pareja]:
    indice = datos.sitios
    s = _buscar(indice, sitio_id)
    if capa not in s.capas:
        raise HTTPException(
            status_code=404,
            detail=f"El sitio {sitio_id} no tiene datos de {capa}. Capas disponibles: {', '.join(s.capas)}",
        )
    return [Pareja(**p) for p in indice.parejas(s, capa)[:n]]
