"""Hielo: análogos de hielo de la Luna y Marte y su comprobación con LRO en el polo sur lunar.

Datos de las capas ``hielo`` (hielo_v0) y ``hielo_lro`` (hielo_v1.1). Ver ``app/hielo.py``.
"""

from collections import Counter
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from app.dependencias import DatosDep
from app.hielo import AVISOS, DatosHielo
from app.schemas import ParejaHielo, ResumenHielo, SitioHielo, SitioHieloDetalle, Veredicto

router = APIRouter(prefix="/hielo", tags=["hielo"])

SIN_HIELO = {404: {"description": "La capa hielo no está en los datos, o el sitio es desconocido"}}
CuerpoId = Literal["luna", "marte"]


def _hielo(datos: DatosDep) -> DatosHielo:
    hielo = datos.hielo
    if not hielo.disponible:
        raise HTTPException(status_code=404, detail="La capa hielo no está en los datos")
    return hielo


@router.get(
    "", response_model=ResumenHielo, summary="Resumen: cuántos análogos de hielo, veredictos y avisos"
)
def resumen(datos: DatosDep) -> ResumenHielo:
    hielo = _hielo(datos)
    sitios = hielo.sitios()
    parejas = hielo.parejas()
    return ResumenHielo(
        versiones={"hielo": hielo.v0.get("version"), "hielo_lro": hielo.lro.get("version")},
        n_sitios=dict(Counter(s["cuerpo"] for s in sitios)),
        n_parejas=dict(Counter(p["cuerpo"] for p in parejas)),
        veredictos=dict(Counter(p["veredicto"] for p in parejas)),
        niveles_lro=dict(Counter(s["nivel_lro"] for s in sitios if s["nivel_lro"])),
        umbrales={
            v: u
            for v, u in (
                (hielo.v0.get("version"), hielo.v0.get("umbrales")),
                (hielo.lro.get("version"), hielo.lro.get("umbrales")),
            )
            if v and u
        },
        avisos=AVISOS,
        fuentes=hielo.lro.get("fuentes", []),
    )


@router.get(
    "/sitios",
    response_model=list[SitioHielo],
    summary="Hielo de cada sitio de la Luna y Marte, con su mejor región de la Tierra",
    responses=SIN_HIELO,
)
def sitios(
    datos: DatosDep,
    cuerpo: Annotated[CuerpoId | None, Query(description="luna o marte")] = None,
    solo_analogos: Annotated[bool, Query(description="Solo los sitios con análogo de hielo")] = False,
) -> list[dict]:
    return [
        s
        for s in _hielo(datos).sitios()
        if (cuerpo is None or s["cuerpo"] == cuerpo) and (not solo_analogos or s["tiene_analogo"])
    ]


@router.get(
    "/sitios/{sitio_id}",
    response_model=SitioHieloDetalle,
    summary="Ficha de hielo de un sitio: 5 regiones de la Tierra y comprobación de LRO",
    responses=SIN_HIELO,
)
def sitio(sitio_id: str, datos: DatosDep) -> dict:
    s = _hielo(datos).sitio(sitio_id)
    if s is None:
        raise HTTPException(status_code=404, detail=f"Sitio sin datos de hielo: {sitio_id}")
    return s


@router.get(
    "/parejas",
    response_model=list[ParejaHielo],
    summary="Análogos de hielo (sitio ↔ región de la Tierra) con su veredicto, de más a menos parecidos",
    responses=SIN_HIELO,
)
def parejas(
    datos: DatosDep,
    cuerpo: Annotated[CuerpoId | None, Query(description="luna o marte")] = None,
    veredicto: Annotated[Veredicto | None, Query(description="Filtra por veredicto")] = None,
) -> list[dict]:
    return [
        p
        for p in _hielo(datos).parejas()
        if (cuerpo is None or p["cuerpo"] == cuerpo) and (veredicto is None or p["veredicto"] == veredicto)
    ]
