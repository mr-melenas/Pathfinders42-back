from fastapi import APIRouter

from app import __version__
from app.config import ajustes
from app.datos import Datos, DatosNoDisponibles, cargar
from app.dependencias import DatosDep
from app.schemas import CapaResumen, Cuerpo, Meta, Salud

router = APIRouter(tags=["estado"])


@router.get("/health", response_model=Salud, summary="Estado de la API")
def health() -> Salud:
    try:
        cargar(str(ajustes().data_dir))
        cargados = True
    except DatosNoDisponibles:
        cargados = False
    return Salud(estado="ok", version_api=__version__, datos_cargados=cargados)


def resumen_capa(datos: Datos, capa_id: str, info: dict) -> CapaResumen:
    archivo = info.get("archivo")
    extras = {
        k: v for k, v in info.items() if k not in {"version", "carpeta", "archivo"} and isinstance(v, str)
    }
    return CapaResumen(
        id=capa_id,
        version=info.get("version"),
        archivo=archivo,
        disponible=bool(archivo and datos.ruta_segura(archivo)),
        extras=extras,
    )


@router.get("/meta", response_model=Meta, summary="Versión de los datos, cuerpos y capas disponibles")
def meta(datos: DatosDep) -> Meta:
    m = datos.manifest
    return Meta(
        proyecto=m.get("proyecto"),
        version_manifest=m.get("version"),
        generado=m.get("generado"),
        version_datos=datos.version,
        cuerpos=[
            Cuerpo(id=k, version=v.get("version"), nombre=v.get("nombre"))
            for k, v in m.get("cuerpos", {}).items()
        ],
        capas=[resumen_capa(datos, k, v) for k, v in datos.capas.items()],
    )
