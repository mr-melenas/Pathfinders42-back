"""Índice de sitios de la Luna y Marte con lo que dice cada capa sobre ellos.

Solo une archivos ya calculados en Colab (por id de sitio) y normaliza sus listas de parejas de la
Tierra a un formato común. No recalcula distancias.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.datos import Datos


def _si_no(valor: Any) -> bool | None:
    """'Sí'/'No', True/False → bool; cualquier otro texto descriptivo → False; vacío → None."""
    if isinstance(valor, bool):
        return valor
    if valor is None:
        return None
    texto = str(valor).strip().lower()
    if texto in {"sí", "si", "true"}:
        return True
    return False if texto else None


@dataclass(frozen=True)
class CapaSitio:
    """Cómo leer una capa con datos por sitio."""

    capa: str  # id de la capa en el manifest
    archivo: str  # clave del manifest con la ruta ("archivo" casi siempre)
    lista: str  # clave de la lista de parejas en cada sitio
    id_: str
    nombre: str
    distancia: str
    parecido_pareja: Callable[[dict, dict], bool | None]  # (pareja, archivo completo) → bool | None
    parecido_sitio: Callable[[dict], bool | None]
    descripcion: str


CAPAS: dict[str, CapaSitio] = {
    "topografia": CapaSitio(
        capa="topografia_sitios",
        archivo="archivo",
        lista="top5_tierra",
        id_="region_id",
        nombre="region",
        distancia="distancia",
        parecido_pareja=lambda p, f: (
            p.get("distancia") is not None and p["distancia"] <= f.get("umbral_parecido", 0.2)
        ),
        parecido_sitio=lambda s: _si_no(s.get("hay_parecido")),
        descripcion="Pendiente y relieve (KS, 0–1). Parecido si la distancia es ≤ 0,2.",
    ),
    "clima": CapaSitio(
        capa="clima",
        archivo="archivo",
        lista="parejas",
        id_="region_id",
        nombre="region",
        distancia="dist_total",
        parecido_pareja=lambda p, f: None,
        parecido_sitio=lambda s: _si_no(s.get("hay_parecido")),
        descripcion="Temperatura de superficie (percentiles) combinada con topografía; brechas en °C.",
    ),
    "geologia": CapaSitio(
        capa="geologia",
        archivo="archivo",
        lista="top5_tierra",
        id_="region_id",
        nombre="region",
        distancia="distancia_total",
        parecido_pareja=lambda p, f: _si_no(p.get("analogo_completo")),
        parecido_sitio=lambda s: _si_no(s.get("hay_analogo_completo")),
        descripcion="Tipo de roca + topografía. Análogo completo si topografía ≤ 0,2 y geología ≤ 0,4.",
    ),
    "hielo": CapaSitio(
        capa="hielo",
        archivo="archivo",
        lista="top5_tierra",
        id_="region_id",
        nombre="region",
        distancia="d_hielo_topo",
        parecido_pareja=lambda p, f: None,
        parecido_sitio=lambda s: _si_no(s.get("analogo_hielo_terreno")),
        descripcion="Hielo cerca de la superficie frente a permafrost de la Tierra, combinado con topografía.",
    ),
    "cuevas": CapaSitio(
        capa="cuevas_v2",
        archivo="archivo",
        lista="parejas",
        id_="id_t",
        nombre="nombre_t",
        distancia="d_combinada",
        parecido_pareja=lambda p, f: None,
        parecido_sitio=lambda s: _si_no(s.get("analogo_cueva")),
        descripcion="Cuevas del mismo tipo en la Tierra: forma (profundidad/diámetro) y terreno.",
    ),
    "anortosita": CapaSitio(
        capa="anortosita",
        archivo="archivo",
        lista="top3",
        id_="id_t",
        nombre="lugar",
        distancia="d_total",
        parecido_pareja=lambda p, f: _si_no(p.get("analogo_completo")),
        parecido_sitio=lambda s: _si_no(s.get("analogo_completo")),
        descripcion="Afloramientos de anortosita (tierras altas lunares): roca + topografía.",
    ),
}

# Geometrías de los sitios: capa del manifest → clave con la ruta del GeoJSON
GEOMETRIAS = [("sitios", "archivo"), ("cuevas_v2", "sitios")]


def _centro(feature: dict) -> tuple[float | None, float | None]:
    props, geom = feature.get("properties", {}), feature.get("geometry") or {}
    if geom.get("type") == "Point":
        lon, lat = geom["coordinates"][:2]
        return lat, lon
    if props.get("lat_centro") is not None:
        return props["lat_centro"], props.get("lon_centro")
    if geom.get("type") == "Polygon":
        anillo = geom["coordinates"][0]
        return sum(p[1] for p in anillo) / len(anillo), sum(p[0] for p in anillo) / len(anillo)
    return None, None


@dataclass
class Sitio:
    id: str
    nombre: str
    cuerpo: str
    tipo: str
    lat: float | None
    lon: float | None
    propiedades: dict[str, Any]
    geometria: dict[str, Any] | None
    capas: dict[str, dict[str, Any]] = field(default_factory=dict)  # capa → registro del sitio


class IndiceSitios:
    def __init__(self, datos: "Datos"):
        self.datos = datos
        self.archivos: dict[str, dict] = {}
        self.sitios: dict[str, Sitio] = {}
        for capa, clave in GEOMETRIAS:
            gj = datos.leer_json(datos.capas.get(capa, {}).get(clave)) or {}
            for f in gj.get("features", []):
                props = dict(f.get("properties", {}))
                sid = props.get("id")
                if not sid:
                    continue
                lat, lon = _centro(f)
                self.sitios[sid] = Sitio(
                    id=sid,
                    nombre=props.get("nombre", sid),
                    cuerpo=props.get("cuerpo", ""),
                    tipo=props.get("tipo", ""),
                    lat=lat,
                    lon=lon,
                    propiedades=props,
                    geometria=f.get("geometry"),
                )
        for nombre, cfg in CAPAS.items():
            archivo = datos.leer_json(datos.capas.get(cfg.capa, {}).get(cfg.archivo))
            if not isinstance(archivo, dict):
                continue
            self.archivos[nombre] = archivo
            for sid, registro in (archivo.get("sitios") or {}).items():
                if sid in self.sitios:
                    self.sitios[sid].capas[nombre] = registro

    def parejas(self, sitio: Sitio, capa: str) -> list[dict[str, Any]]:
        cfg = CAPAS[capa]
        registro = sitio.capas.get(capa) or {}
        archivo = self.archivos.get(capa, {})
        salida = []
        for p in registro.get(cfg.lista) or []:
            detalles = {k: v for k, v in p.items() if k not in {cfg.id_, cfg.nombre}}
            salida.append(
                {
                    "id": p.get(cfg.id_),
                    "nombre": p.get(cfg.nombre) or p.get(cfg.id_) or "",
                    "distancia": p.get(cfg.distancia),
                    "parecido": cfg.parecido_pareja(p, archivo),
                    "detalles": detalles,
                }
            )
        # Primero las que la capa marca como análogo; dentro de cada grupo, de menor a mayor distancia
        return sorted(
            salida, key=lambda x: (x["parecido"] is not True, x["distancia"] is None, x["distancia"] or 0)
        )

    def resumen(self, sitio: Sitio) -> list[dict[str, Any]]:
        salida = []
        for capa, registro in sitio.capas.items():
            parejas = self.parejas(sitio, capa)
            salida.append(
                {
                    "capa": capa,
                    "descripcion": CAPAS[capa].descripcion,
                    "hay_parecido": CAPAS[capa].parecido_sitio(registro),
                    "mejor": parejas[0] if parejas else None,
                    "n_parejas": len(parejas),
                }
            )
        return salida
