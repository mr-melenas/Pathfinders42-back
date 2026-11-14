"""Lectura de los resultados de M1 (``capas.m1`` del manifest). No entrena ni predice nada."""

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.datos import Datos


class ResultadosM1:
    def __init__(self, datos: "Datos", info: dict[str, Any]):
        self.datos = datos
        self.info = info
        self.resultado: dict[str, Any] = datos.leer_json(info.get("archivo")) or {}
        self.familias: dict[str, dict[str, Any]] = self.resultado.get("familias", {})

    @property
    def disponible(self) -> bool:
        return bool(self.familias)

    @cached_property
    def candidatos(self) -> dict[str, dict[str, Any]]:
        return {c["id"]: c for f in self.familias.values() for c in f.get("candidatos", [])}

    @cached_property
    def geojson(self) -> dict[str, Any]:
        return self.datos.leer_json(self.info.get("geojson")) or {"type": "FeatureCollection", "features": []}

    def ruta_mapa(self, familia: str) -> Path | None:
        ruta = (self.info.get("mapas") or {}).get(familia)
        return self.datos.ruta_segura(ruta) if isinstance(ruta, str) else None
