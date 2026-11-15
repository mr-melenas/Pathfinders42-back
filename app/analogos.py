"""Fichas de análogos: pros y contras de cada pareja sitio (Luna/Marte) ↔ lugar de la Tierra.

Lee la capa ``analogos`` (``analogos_v0/analogos.json``, generada por ``scripts/construir_analogos.py``). No
recalcula nada: filtra y devuelve lo que ya viene en el archivo.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.datos import Datos


class DatosAnalogos:
    def __init__(self, datos: "Datos"):
        info = datos.capas.get("analogos") or {}
        self.archivo: dict[str, Any] = datos.leer_json(info.get("archivo")) or {}
        self.disponible = bool(self.archivo.get("sitios"))

    def sitio(self, sitio_id: str) -> dict[str, Any] | None:
        return self.archivo.get("sitios", {}).get(sitio_id)

    def ficha(self, sitio_id: str, tierra_id: str) -> dict[str, Any] | None:
        sitio = self.sitio(sitio_id)
        if sitio is None:
            return None
        return next((a for a in sitio["analogos"] if a["tierra_id"] == tierra_id), None)

    def limites(self, cuerpo: str) -> list[dict[str, Any]]:
        return self.archivo.get("limites_tierra", {}).get(cuerpo, [])
