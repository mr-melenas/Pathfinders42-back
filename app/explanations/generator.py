"""
ES: Convierte la ficha de un sitio (respuesta de GET /sitios/{id}) en una explicación. No hay modelo
generativo: cada cifra viene de la ficha y cada afirmación sobre límites viene de un fragmento del
corpus con su fuente. Sin corpus, `limites` queda vacío.
EN: Turns a site record (GET /sitios/{id} response) into an explanation. There is no generative
model: every figure comes from the record and every limits claim comes from a corpus fragment
with its source. Without a corpus, `limites` stays empty.
"""

from .index import TextIndex

# ES: Veredicto de la API -> etiqueta de salida (contrato en español). None = la capa no decide.
# EN: API verdict -> output label (Spanish contract). None = the layer does not decide.
STATES = {True: "funciona", False: "falla", None: "no_decide"}
LIMITS_QUERY = "límites de la Tierra como análogo gravedad vacío atmósfera radiación"


def _layer_text(layer: str, state: str, best: dict | None, gaps: dict) -> str:
    """
    ES: Frase de una capa a partir de su veredicto, su mejor pareja y sus brechas (°C).
    EN: One layer's sentence from its verdict, best match and gaps (°C).
    """
    if state == "no_decide":
        text = f"Capa {layer}: la capa no decide por pareja."
    elif best is None:
        return f"Capa {layer}: {state}, sin parejas disponibles."
    elif state == "funciona":
        text = f"Capa {layer}: funciona."
    else:
        text = f"Capa {layer}: falla; ninguna pareja alcanza el umbral de parecido."
    if best:
        text += (
            f" Mejor pareja: {best['nombre']} (distancia {best['distancia']}, similitud {best['similitud']})."
        )
    if gaps:
        text += (
            " "
            + "; ".join(
                f"brecha {key.removeprefix('brecha_').replace('_', ' ')}: {value} °C"
                for key, value in gaps.items()
            )
            + "."
        )
    return text


def explain_record(record: dict, index: TextIndex | None = None) -> dict:
    """
    ES: Genera la explicación de un sitio. `index` (opcional) aporta los límites con su fuente.
    EN: Builds a site's explanation. `index` (optional) supplies the limits with their source.
    """
    layers = []
    for entry in record.get("resumen", []):
        state = STATES[entry.get("hay_parecido")]
        best_raw = entry.get("mejor")
        details = (best_raw or {}).get("detalles", {})
        # ES: "brecha_*" son diferencias en °C; el resto de detalles se copian tal cual.
        # EN: "brecha_*" are °C differences; the other details are copied as they come.
        gaps = {k: v for k, v in details.items() if k.startswith("brecha_")}
        other_details = {k: v for k, v in details.items() if k not in gaps}
        match = None
        if best_raw:
            match = {
                "id": best_raw["id"],
                "nombre": best_raw["nombre"],
                "distancia": best_raw["distancia"],
                "similitud": round(1 - best_raw["distancia"], 3),
                "parecido": best_raw.get("parecido"),
            }
        layers.append(
            {
                "capa": entry["capa"],
                "descripcion": entry.get("descripcion"),
                "estado": state,
                "n_parejas": entry.get("n_parejas"),
                "pareja": match,
                "brechas": gaps,
                "detalles": other_details,
                "texto": _layer_text(entry["capa"], state, match, gaps),
            }
        )

    def names_with(state: str) -> list[str]:
        return [layer["capa"] for layer in layers if layer["estado"] == state]

    works, fails, undecided = names_with("funciona"), names_with("falla"), names_with("no_decide")
    parts = [
        f"{record['nombre']} ({record['cuerpo']})",
        f"funciona en {len(works)} capa(s)" + (f": {', '.join(works)}" if works else ""),
        f"falla en {len(fails)}" + (f": {', '.join(fails)}" if fails else ""),
    ]
    if undecided:
        parts.append(f"sin veredicto por pareja en: {', '.join(undecided)}")

    limits = []
    if index:
        limits = [
            {"fuente": f["fuente"], "url": f.get("url"), "texto": f["texto"]}
            for f in index.search(LIMITS_QUERY, k=3, kind="limites")
        ]

    properties = record.get("propiedades", {})
    return {
        "sitio_id": record["id"],
        "nombre": record["nombre"],
        "cuerpo": record["cuerpo"],
        "resumen": ". ".join(parts) + ".",
        "donde_funciona": works,
        "donde_falla": fails,
        "sin_veredicto": undecided,
        "capas": layers,
        "limites": limits,
        "fuente_sitio": {"fuente": properties.get("fuente"), "url": properties.get("url_fuente")},
    }
