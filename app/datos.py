"""Acceso a los datos precalculados de 06_web.

La API no calcula nada: lee los archivos que exportan los notebooks de Colab
(copiados a data/06_web con scripts/sync_data.py). El punto de entrada es manifest.json.
"""

import json
from functools import cached_property, lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.analogos import DatosAnalogos
    from app.hielo import DatosHielo
    from app.m1 import ResultadosM1
    from app.sitios import IndiceSitios
    from app.usos import DatosUsos


class DatosNoDisponibles(RuntimeError):
    """No hay manifest.json en la carpeta de datos."""


class Datos:
    def __init__(self, carpeta: Path):
        self.carpeta = carpeta.resolve()
        ruta = self.carpeta / "manifest.json"
        if not ruta.is_file():
            raise DatosNoDisponibles(f"No se encuentra {ruta}. Ejecuta scripts/sync_data.py")
        self.manifest: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
        self._cache_json: dict[str, Any] = {}
        version = self.carpeta.parent / "VERSION.json"
        if not version.is_file():
            version = self.carpeta / "VERSION.json"
        self.version: dict[str, Any] | None = (
            json.loads(version.read_text(encoding="utf-8")) if version.is_file() else None
        )

    @property
    def capas(self) -> dict[str, dict[str, Any]]:
        return self.manifest.get("capas", {})

    def ruta_segura(self, relativa: str) -> Path | None:
        """Ruta absoluta de un archivo del manifest, sin salir de la carpeta de datos."""
        ruta = (self.carpeta / relativa).resolve()
        if not ruta.is_relative_to(self.carpeta) or not ruta.is_file():
            return None
        return ruta

    def leer_json(self, relativa: str | None) -> Any | None:
        """JSON de un archivo del manifest (None si falta). Se cachea: los datos no cambian en caliente."""
        if not relativa:
            return None
        if relativa not in self._cache_json:
            ruta = self.ruta_segura(relativa)
            self._cache_json[relativa] = json.loads(ruta.read_text(encoding="utf-8")) if ruta else None
        return self._cache_json[relativa]

    @cached_property
    def sitios(self) -> "IndiceSitios":
        from app.sitios import IndiceSitios

        return IndiceSitios(self)

    @cached_property
    def hielo(self) -> "DatosHielo":
        from app.hielo import DatosHielo

        return DatosHielo(self)

    @cached_property
    def analogos(self) -> "DatosAnalogos":
        from app.analogos import DatosAnalogos

        return DatosAnalogos(self)

    @cached_property
    def usos(self) -> "DatosUsos":
        from app.usos import DatosUsos

        return DatosUsos(self)

    @cached_property
    def m1(self) -> "ResultadosM1 | None":
        """Resultados de M1, o None si la capa no está en el manifest."""
        from app.m1 import ResultadosM1

        info = self.capas.get("m1")
        return ResultadosM1(self, info) if info else None


@lru_cache
def cargar(carpeta: str) -> Datos:
    return Datos(Path(carpeta))
