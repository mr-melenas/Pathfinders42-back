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


# Brechas = sitio − Tierra en °C: en temperaturas, negativo = el sitio es más frío; en oscilaciones y
# amplitudes, negativo = el sitio varía menos.
GAP_NAMES = {
    "ts_media": ("temperatura media", "más fría", "más cálida"),
    "ts_min": ("temperatura mínima", "más fría", "más cálida"),
    "ts_max": ("temperatura máxima", "más fría", "más cálida"),
    "t_interior": ("temperatura interior", "más fría", "más cálida"),
    "osc_diaria": ("oscilación diaria", "menor", "mayor"),
    "amplitud_anual": ("amplitud anual", "menor", "mayor"),
}


def _num(value: float, decimals: int = 2) -> str:
    """Número en formato español (coma decimal)."""
    return f"{value:.{decimals}f}".replace(".", ",")


def _gap_text(key: str, value: float, place: str) -> str:
    name, lower, higher = GAP_NAMES.get(key, (key.replace("_", " "), "menor", "mayor"))
    if round(value) == 0:
        return f"{name}: casi igual que en {place}"
    return f"{name}: {_num(abs(value), 0)} °C {lower if value < 0 else higher} que en {place}"


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
        if best.get("distancia") is None:
            text += f" Mejor pareja: {best['nombre']}."
        else:
            text += f" Mejor pareja: {best['nombre']} (distancia {_num(best['distancia'])}; 0 = igual)."
    gaps = {k: v for k, v in gaps.items() if v is not None}
    if gaps:
        place = best["nombre"] if best else "la Tierra"
        text += (
            " En el sitio, "
            + "; ".join(_gap_text(k.removeprefix("brecha_"), v, place) for k, v in gaps.items())
            + "."
        )
    return text


def uses_summary(uses: dict[str, dict], names: dict[str, str]) -> tuple[list[dict], str]:
    """
    ES: Mejor pareja de cada uso de misión (capa usos_v0): qué capas funcionan y fallan con ESE lugar.
    EN: Best match per mission use (usos_v0 layer): which layers work and fail with THAT place.
    """
    rows, sentences = [], []
    for use_id, best in uses.items():
        if not best:
            continue
        row = {
            "uso": names.get(use_id, use_id),
            "pareja": best["tierra_nombre"],
            "puntuacion": best["puntuacion"],
            "apta": best["apta"],
            "funciona": best["funciona"],
            "falla": best["falla"],
            "sin_dato": best.get("sin_dato", []),
        }
        rows.append(row)
        verdict = "apta" if best["apta"] else "no apta"
        detail = f"funciona en {', '.join(best['funciona']) or 'ninguna capa'}"
        if best["falla"]:
            detail += f"; falla en {', '.join(best['falla'])}"
        sentences.append(f"{row['uso']}: {best['tierra_nombre']} ({verdict}; {detail})")
    text = ("Mejor análogo por uso de misión. " + ". ".join(sentences) + ".") if sentences else ""
    return rows, text


def explain_record(
    record: dict,
    index: TextIndex | None = None,
    uses: dict[str, dict] | None = None,
    use_names: dict[str, str] | None = None,
) -> dict:
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

    use_rows, use_text = uses_summary(uses or {}, use_names or {})
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
        "por_uso": use_rows,
        "texto_usos": use_text,
        "limites": limits,
        "fuente_sitio": {"fuente": properties.get("fuente"), "url": properties.get("url_fuente")},
    }
