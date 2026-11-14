"""Usos de misión (enfoque D): mejores análogos de la Tierra según para qué se quieran.

Datos de la capa ``usos`` (usos_v0). Ver ``app/usos.py`` y ``scripts/construir_usos.py``.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from app.dependencias import DatosDep
from app.schemas import ParejaUso, RankingSitio, Uso, Usos
from app.usos import DatosUsos

router = APIRouter(prefix="/usos", tags=["usos"])

NO_ENCONTRADO = {404: {"description": "Capa usos ausente, uso desconocido o sitio sin parejas"}}


def _usos(datos: DatosDep, uso: str | None = None) -> DatosUsos:
    u = datos.usos
    if not u.disponible:
        raise HTTPException(status_code=404, detail="La capa usos no está en los datos")
    if uso is not None and uso not in u.usos:
        raise HTTPException(status_code=404, detail=f"Uso desconocido: {uso}. Usos: {', '.join(u.usos)}")
    return u


@router.get("", response_model=Usos, summary="Usos de misión con sus pesos por capa", responses=NO_ENCONTRADO)
def listar(datos: DatosDep) -> Usos:
    u = _usos(datos)
    return Usos(
        version=u.archivo.get("version"),
        umbrales=u.umbrales,
        usos=[Uso(**cfg, n_sitios=u.n_sitios(cfg["id"])) for cfg in u.usos.values()],
        nota=u.archivo.get("nota"),
    )


@router.get(
    "/{uso}/sitios/{sitio_id}",
    response_model=list[ParejaUso],
    summary="Análogos de la Tierra de un sitio para un uso, de mejor a peor",
    responses=NO_ENCONTRADO,
)
def parejas(
    uso: str,
    sitio_id: str,
    datos: DatosDep,
    n: Annotated[int, Query(ge=1, le=50, description="Número máximo de parejas")] = 10,
    solo_aptas: Annotated[bool, Query(description="Solo las que pasan las capas obligatorias")] = False,
) -> list[ParejaUso]:
    u = _usos(datos, uso)
    lista = u.parejas(sitio_id, uso, solo_aptas)
    if lista is None:
        raise HTTPException(status_code=404, detail=f"Sitio desconocido o sin parejas: {sitio_id}")
    return [ParejaUso(**p) for p in lista[:n]]


@router.get(
    "/{uso}/ranking",
    response_model=list[RankingSitio],
    summary="Mejor análogo de cada sitio para un uso (los sitios con pareja apta primero)",
    responses=NO_ENCONTRADO,
)
def ranking(
    uso: str,
    datos: DatosDep,
    cuerpo: Annotated[Literal["luna", "marte"] | None, Query()] = None,
    tipo: Annotated[str | None, Query(description="p. ej. region_aterrizaje_artemis, cueva_marte")] = None,
    n: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[RankingSitio]:
    u = _usos(datos, uso)
    filas = []
    for s in datos.sitios.sitios.values():
        if (cuerpo and s.cuerpo != cuerpo) or (tipo and s.tipo != tipo):
            continue
        lista = u.parejas(s.id, uso) or []
        if not lista:
            continue
        filas.append(
            RankingSitio(
                sitio_id=s.id,
                nombre=s.nombre,
                cuerpo=s.cuerpo,
                tipo=s.tipo,
                lat=s.lat,
                lon=s.lon,
                n_aptas=sum(p["apta"] for p in lista),
                mejor=ParejaUso(**lista[0]),
            )
        )
    por_capas = u.usos[uso].get("orden") == "capas_ok"
    filas.sort(key=lambda f: (not f.mejor.apta, -f.mejor.n_capas_ok if por_capas else 0, -f.mejor.puntuacion))
    return filas[:n]
