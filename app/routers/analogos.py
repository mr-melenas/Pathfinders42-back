"""Fichas de análogos: pros y contras de cada lugar de la Tierra para un sitio de la Luna o Marte.

Datos de la capa ``analogos`` (analogos_v0). Ver ``app/analogos.py`` y ``scripts/construir_analogos.py``.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.analogos import DatosAnalogos
from app.dependencias import DatosDep
from app.schemas import AnalogoFicha, AnalogoResumen

router = APIRouter(prefix="/analogos", tags=["analogos"])

NO_ENCONTRADO = {404: {"description": "Capa analogos ausente, sitio sin análogos o lugar que no es pareja"}}


def _analogos(datos: DatosDep) -> DatosAnalogos:
    a = datos.analogos
    if not a.disponible:
        raise HTTPException(status_code=404, detail="La capa analogos no está en los datos")
    return a


def _resumen(f: dict) -> AnalogoResumen:
    return AnalogoResumen(
        **{k: f[k] for k in AnalogoResumen.model_fields if k in f},
        n_pros=len(f["pros"]),
        n_contras=len(f["contras"]),
    )


@router.get(
    "/{sitio_id}",
    response_model=list[AnalogoResumen],
    summary="Análogos de la Tierra de un sitio, con su frase de pros y contras (aptos primero)",
    responses=NO_ENCONTRADO,
)
def listar(
    sitio_id: str,
    datos: DatosDep,
    n: Annotated[int, Query(ge=1, le=100, description="Número máximo de análogos")] = 20,
    solo_aptos: Annotated[bool, Query(description="Solo los que pasan al menos 2 capas")] = False,
    verificacion: Annotated[
        str | None, Query(description="verificada, pendiente, candidato o hipótesis")
    ] = None,
) -> list[AnalogoResumen]:
    sitio = _analogos(datos).sitio(sitio_id)
    if sitio is None:
        raise HTTPException(status_code=404, detail=f"Sitio desconocido o sin análogos: {sitio_id}")
    fichas = [
        f
        for f in sitio["analogos"]
        if (not solo_aptos or f["apta"]) and (verificacion is None or f["verificacion"] == verificacion)
    ]
    return [_resumen(f) for f in fichas[:n]]


@router.get(
    "/{sitio_id}/{tierra_id}",
    response_model=AnalogoFicha,
    summary="Ficha de un análogo: pros, contras, capas sin medir y límites de la Tierra",
    responses=NO_ENCONTRADO,
)
def ficha(sitio_id: str, tierra_id: str, datos: DatosDep) -> AnalogoFicha:
    a = _analogos(datos)
    sitio = a.sitio(sitio_id)
    f = a.ficha(sitio_id, tierra_id)
    if sitio is None or f is None:
        raise HTTPException(status_code=404, detail=f"{tierra_id} no es pareja de {sitio_id}")
    return AnalogoFicha(
        **_resumen(f).model_dump(),
        **{k: f[k] for k in ("ficha_id", "rasgo", "referencia", "url", "pros", "contras", "sin_dato")},
        sitio_id=sitio_id,
        sitio_nombre=sitio["nombre"],
        cuerpo=sitio["cuerpo"],
        limites_tierra=a.limites(sitio["cuerpo"]),
    )
