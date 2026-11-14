from typing import Annotated

from fastapi import Depends, HTTPException

from app.config import ajustes
from app.datos import Datos, DatosNoDisponibles, cargar


def obtener_datos() -> Datos:
    try:
        return cargar(str(ajustes().data_dir))
    except DatosNoDisponibles as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


DatosDep = Annotated[Datos, Depends(obtener_datos)]
