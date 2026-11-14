from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.dependencias import DatosDep
from app.routers.salud import resumen_capa
from app.schemas import CapaResumen

router = APIRouter(prefix="/capas", tags=["capas"])


@router.get("", response_model=list[CapaResumen], summary="Capas registradas en el manifest")
def listar(datos: DatosDep) -> list[CapaResumen]:
    return [resumen_capa(datos, k, v) for k, v in datos.capas.items()]


@router.get(
    "/{capa}",
    summary="Archivo completo de una capa (JSON o GeoJSON, tal como lo exporta Colab)",
    responses={404: {"description": "Capa desconocida o archivo no sincronizado"}},
)
def obtener(capa: str, datos: DatosDep) -> FileResponse:
    info = datos.capas.get(capa)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Capa desconocida: {capa}")
    ruta = datos.ruta_segura(info.get("archivo", ""))
    if ruta is None:
        raise HTTPException(status_code=404, detail=f"El archivo de la capa {capa} no está sincronizado")
    tipo = "application/geo+json" if ruta.suffix == ".geojson" else "application/json"
    return FileResponse(ruta, media_type=tipo)
