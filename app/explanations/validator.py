"""
ES: Valida que un texto generado por un LLM no contenga cifras ni citas [n] ausentes de sus entradas.
EN: Checks that LLM-generated text contains no figures or [n] citations missing from its inputs.
"""

import re

# ES: "1.200" (millares) se prueba antes que el decimal simple. EN: "1.200" (thousands) is tried before a plain decimal.
NUMBER_PATTERN = re.compile(r"\d{1,3}(?:\.\d{3})+(?!\d)|\d+(?:[.,]\d+)?")
CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def _token_values(token: str) -> list[float]:
    """
    ES: Valores posibles de un token numérico: "1.200" puede ser 1.2 (decimal) o 1200 (millares).
    EN: Possible values of a numeric token: "1.200" may be 1.2 (decimal) or 1200 (thousands).
    """
    values = [float(token.replace(",", ".")) if token.count(".") <= 1 else None]
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token):
        values.append(float(token.replace(".", "")))
    return [v for v in values if v is not None]


def extract_numbers(text: str) -> list[float]:
    """
    ES: Extrae los números de un texto (coma decimal admitida); para "1.200" devuelve la lectura decimal.
    EN: Extracts numbers (comma decimals allowed); for "1.200" returns the decimal reading.
    """
    return [(_token_values(t) or [0.0])[0] for t in NUMBER_PATTERN.findall(text)]


def _collect(value, allowed: set) -> None:
    """
    ES: Recoge recursivamente todos los números de un JSON, con redondeos de 0 a 3 decimales.
    EN: Recursively collects every number in a JSON value, with 0-3 decimal roundings.
    """
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        magnitude = abs(float(value))
        allowed.add(round(magnitude, 9))
        for decimals in (0, 1, 2, 3):
            allowed.add(round(magnitude, decimals))
    elif isinstance(value, str):
        for token in NUMBER_PATTERN.findall(value):
            allowed.update(round(v, 9) for v in _token_values(token))
    elif isinstance(value, dict):
        for item in value.values():
            _collect(item, allowed)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect(item, allowed)


def invalid_figures(text: str, *inputs, free_up_to: int = 10) -> list[float]:
    """
    ES: Devuelve las cifras del texto que no aparecen en las entradas (JSON, fragmentos...). Se ignora
    el signo, las citas [n] y los enteros pequeños (recuentos como «2 capas»); los decimales deben coincidir.
    EN: Returns the figures in the text that do not appear in the inputs (JSON, fragments...). Sign,
    [n] citations and small integers (counts like "2 layers") are ignored; decimals must match.
    """
    allowed: set[float] = set()
    for item in inputs:
        _collect(item, allowed)
    invalid = []
    for token in NUMBER_PATTERN.findall(CITATION_PATTERN.sub("", text)):
        values = _token_values(token)
        if not values:
            continue
        if any(v == int(v) and v <= free_up_to for v in values):
            continue
        if not any(round(v, 9) in allowed for v in values):
            invalid.append(values[0])
    return invalid


def invalid_citations(text: str, fragment_count: int) -> list[int]:
    """
    ES: Citas [n] fuera de rango (n < 1 o n > nº de fragmentos). EN: Out-of-range [n] citations.
    """
    return [n for n in map(int, CITATION_PATTERN.findall(text)) if n < 1 or n > fragment_count]
