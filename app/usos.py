"""Usos de misión (enfoque D): parejas sitio ↔ Tierra puntuadas por uso.

Lee la capa ``usos`` (``usos_v0/usos.json``, generada por ``scripts/construir_usos.py``). No recalcula
puntuaciones: solo filtra y ordena las que ya vienen en el archivo.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.datos import Datos


class DatosUsos:
    def __init__(self, datos: "Datos"):
        info = datos.capas.get("usos") or {}
        self.archivo: dict[str, Any] = datos.leer_json(info.get("archivo")) or {}
        self.disponible = bool(self.archivo.get("sitios"))
        self.usos: dict[str, dict[str, Any]] = {u["id"]: u for u in self.archivo.get("usos", [])}
        self.umbrales: dict[str, float] = self.archivo.get("umbrales", {})

    def n_sitios(self, uso: str) -> int:
        return sum(
            any(uso in p["usos"] for p in s["parejas"]) for s in self.archivo.get("sitios", {}).values()
        )

    def parejas(self, sitio_id: str, uso: str, solo_aptas: bool = False) -> list[dict[str, Any]] | None:
        """Parejas de un sitio para un uso, de mejor a peor. None si el sitio no está en la capa."""
        sitio = self.archivo.get("sitios", {}).get(sitio_id)
        if sitio is None:
            return None
        cfg = self.usos[uso]
        salida = []
        for p in sitio["parejas"]:
            u = p["usos"].get(uso)
            if u is None or (solo_aptas and not u["apta"]):
                continue
            salida.append(
                {
                    **{k: v for k, v in p.items() if k != "usos"},
                    "puntuacion": u["puntuacion"],
                    "cobertura": u["cobertura"],
                    "apta": u["apta"],
                    "n_capas_ok": u["n_ok"],
                    "sin_dato": [k for k, w in cfg["pesos"].items() if w and k not in p["distancias"]],
                }
            )
        if cfg.get("orden") == "capas_ok":
            clave = lambda p: (not p["apta"], -p["n_capas_ok"], -p["puntuacion"])  # noqa: E731
        else:
            clave = lambda p: (not p["apta"], -p["puntuacion"], -p["cobertura"])  # noqa: E731
        return sorted(salida, key=clave)
