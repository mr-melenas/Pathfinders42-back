"""
ES: Valida que un texto generado por un LLM no contenga cifras ausentes de sus entradas.
EN: Checks that LLM-generated text contains no figures missing from its inputs.
"""

import re

NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")


def extract_numbers(text: str) -> list[float]:
    """
    ES: Extrae los números de un texto (admite coma decimal). EN: Extracts numbers (comma decimals allowed).
    """
    return [float(m.replace(",", ".")) for m in NUMBER_PATTERN.findall(text)]


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
        allowed.update(round(n, 9) for n in extract_numbers(value))
    elif isinstance(value, dict):
        for item in value.values():
            _collect(item, allowed)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect(item, allowed)


def invalid_figures(text: str, *inputs, free_up_to: int = 10) -> list[float]:
    """
    ES: Devuelve las cifras del texto que no aparecen en las entradas (JSON, fragmentos...). Se ignora
    el signo y los enteros pequeños (recuentos como «2 capas»); los decimales deben coincidir.
    EN: Returns the figures in the text that do not appear in the inputs (JSON, fragments...). Sign and
    small integers (counts like "2 layers") are ignored; decimals must match.
    """
    allowed: set[float] = set()
    for item in inputs:
        _collect(item, allowed)
    invalid = []
    for number in extract_numbers(text):
        if number == int(number) and number <= free_up_to:
            continue
        if round(number, 9) not in allowed:
            invalid.append(number)
    return invalid
