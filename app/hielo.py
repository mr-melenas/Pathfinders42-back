"""Hielo: une la pareja con la Tierra de ``hielo_v0`` (Luna y Marte) con la comprobación de LRO de
``hielo_v1.1`` (solo los 12 sitios lunares por debajo de −80°).

No recalcula nada: lee los dos JSON del manifest (capas ``hielo`` y ``hielo_lro``) y traduce el nivel
de LRO a un veredicto de la pareja con una tabla fija (``VEREDICTOS``).
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.datos import Datos

# nivel de hielo_v1.1 → (veredicto de la pareja con la Tierra, motivo)
VEREDICTOS: dict[str, tuple[str, str]] = {
    "frío + hidrógeno": (
        "se mantiene",
        "Diviner y LEND coinciden: hace frío para que el hielo sea estable y hay más hidrógeno que en "
        "el resto del polo. El hidrógeno es de la región (unos 20 km), no del sitio exacto.",
    ),
    "solo frío": (
        "debilitada",
        "El hielo sería estable, pero LEND no ve más hidrógeno que en el resto del polo: la analogía "
        "vale para la temperatura, no para hielo presente.",
    ),
    "solo hidrógeno": (
        "debilitada",
        "LEND ve más hidrógeno que en el resto del polo, pero no hace frío suficiente para que el hielo "
        "sea estable cerca de la superficie.",
    ),
    "sin señal": ("no se sostiene", "Ni Diviner ni LEND apoyan que haya hielo en el sitio."),
}
SIN_COMPROBAR = "sin comprobar"

AVISOS = [
    "LEND no separa lugares a menos de unos 20 km: su hidrógeno es regional.",
    "La supresión de LEND solo sirve para comparar lugares entre sí (no se resta el fondo de la nave).",
    "Mini-RF mide rugosidad a escala de decímetros (bloques), no hielo.",
    "En Marte el hielo sale de una sola fuente (SWIM, a menos de 5 m): las parejas están sin comprobar.",
    "En la Tierra hay hielo masivo; en la Luna, hidrógeno escaso y repartido. La analogía funciona en "
    "temperatura y estabilidad, no en cantidad.",
]

# Campos de hielo_v1.1 que se publican, con su nombre en la respuesta
CAMPOS_LRO = {
    "nivel_hielo": "nivel",
    "diviner_f_hielo": "diviner_f_hielo",
    "senal_diviner": "senal_diviner",
    "lend_supresion": "lend_supresion",
    "lend_err": "lend_err",
    "lend_exceso": "lend_exceso",
    "lend_z_polo": "lend_z_polo",
    "lend_percentil": "lend_percentil",
    "senal_lend": "senal_lend",
    "lend_radios_con_senal": "lend_radios_con_senal",
    "lend_robusta": "lend_robusta",
    "minirf_frac_cpr_gt1": "minirf_frac_cpr_gt1",
    "rugosidad_radar_percentil": "rugosidad_radar_percentil",
    "rugosidad_radar": "rugosidad_radar",
}


def _tiene_analogo(valor: Any) -> bool | None:
    """'Sí' → True, 'No' → False, '—' o vacío (sin datos para comparar) → None."""
    texto = str(valor or "").strip().lower()
    return {"sí": True, "si": True, "no": False}.get(texto)


class DatosHielo:
    def __init__(self, datos: "Datos"):
        self.v0: dict[str, Any] = datos.leer_json(datos.capas.get("hielo", {}).get("archivo")) or {}
        self.lro: dict[str, Any] = datos.leer_json(datos.capas.get("hielo_lro", {}).get("archivo")) or {}

    @property
    def disponible(self) -> bool:
        return bool(self.v0.get("sitios"))

    def comprobacion(self, sitio_id: str) -> dict[str, Any] | None:
        registro = (self.lro.get("sitios") or {}).get(sitio_id)
        if registro is None:
            return None
        return {salida: registro.get(campo) for campo, salida in CAMPOS_LRO.items()}

    def sitio(self, sitio_id: str) -> dict[str, Any] | None:
        s = (self.v0.get("sitios") or {}).get(sitio_id)
        if s is None:
            return None
        lro = self.comprobacion(sitio_id)
        regiones = s.get("top5_tierra") or []
        return {
            "id": sitio_id,
            "nombre": s.get("nombre", sitio_id),
            "cuerpo": s.get("cuerpo", ""),
            "tipo": s.get("tipo", ""),
            "lat": s.get("lat"),
            "lon": s.get("lon"),
            "f_hielo": s.get("f_hielo"),
            "fuente_hielo": s.get("fuente_hielo"),
            "tiene_analogo": _tiene_analogo(s.get("analogo_hielo_terreno")),
            "mejor_region": s.get("region_ht"),
            "d_hielo_topo": s.get("d_hielo_topo_ht"),
            "nivel_lro": lro["nivel"] if lro else None,
            # solo en la ficha
            "h2o_grs_pct": s.get("h2o_grs_pct"),
            "regiones": regiones,
            "lro": lro,
        }

    def sitios(self) -> list[dict[str, Any]]:
        return [self.sitio(sid) for sid in self.v0.get("sitios") or {}]

    def pareja(self, sitio: dict[str, Any]) -> dict[str, Any] | None:
        """Pareja de hielo del sitio (solo si hielo_v0 la marca como análogo), con su veredicto."""
        if not sitio["tiene_analogo"]:
            return None
        # La región de la pareja es la de region_ht; hielo_v0 la deja la primera de top5_tierra
        region = next((r for r in sitio["regiones"] if r.get("region") == sitio["mejor_region"]), None)
        if region is None and sitio["regiones"]:
            region = min(sitio["regiones"], key=lambda r: r.get("d_hielo_topo") or 1.0)
        if region is None:
            return None
        lro = sitio["lro"]
        if lro and lro["nivel"] in VEREDICTOS:
            veredicto, motivo = VEREDICTOS[lro["nivel"]]
        else:
            veredicto = SIN_COMPROBAR
            motivo = f"Solo hay una fuente de hielo para este sitio: {sitio['fuente_hielo']}."
        return {
            "sitio_id": sitio["id"],
            "sitio": sitio["nombre"],
            "cuerpo": sitio["cuerpo"],
            "f_hielo_sitio": sitio["f_hielo"],
            "fuente_hielo": sitio["fuente_hielo"],
            "region": region,
            "veredicto": veredicto,
            "motivo": motivo,
            "nivel_lro": lro["nivel"] if lro else None,
        }

    def parejas(self) -> list[dict[str, Any]]:
        salida = [p for s in self.sitios() if (p := self.pareja(s))]
        return sorted(salida, key=lambda p: (p["cuerpo"], p["region"].get("d_hielo_topo") or 1.0))
