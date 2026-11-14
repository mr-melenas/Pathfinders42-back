"""
ES: Construye data/rag/corpus.jsonl a partir de data/rag/sources/ y data/rag/sources.csv, con columnas
archivo,fuente,url,tipo,sitio_id,analogo_id. `tipo`: paper, dataset, ficha o limites (notas de
gravedad, vacío, atmósfera y radiación).
EN: Builds data/rag/corpus.jsonl from data/rag/sources/ and data/rag/sources.csv, with columns
archivo,fuente,url,tipo,sitio_id,analogo_id. `tipo`: paper, dataset, ficha or limites (notes on
gravity, vacuum, atmosphere and radiation).
"""

import csv
import json
import re
from pathlib import Path

ROOT = Path("data/rag")
CHUNK_SIZE, OVERLAP = 1200, 150  # characters (~300 tokens) / caracteres
LIMIT = (
    CHUNK_SIZE - OVERLAP - 2
)  # ES: el solape y el \n\n se suman a cada pieza / EN: overlap and \n\n are added


def _split_long(paragraph: str) -> list[str]:
    """
    ES: Parte un párrafo más largo que LIMIT por frases (y por palabras si una frase es enorme).
    EN: Splits a paragraph longer than LIMIT by sentences (and by words if a sentence is huge).
    """
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
        while len(sentence) > LIMIT:  # hard cut at a word boundary / corte duro en límite de palabra
            cut = sentence.rfind(" ", 0, LIMIT) or LIMIT
            cut = cut if cut > 0 else LIMIT
            pieces.append(sentence[:cut])
            sentence = sentence[cut:].lstrip()
        if current and len(current) + len(sentence) + 1 > LIMIT:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def split_text(text: str) -> list[str]:
    """
    ES: Trocea por párrafos hasta ~CHUNK_SIZE caracteres, con solape. EN: Splits by paragraph up to ~CHUNK_SIZE characters, with overlap.
    """
    paragraphs = [
        piece
        for p in text.split("\n\n")
        if p.strip()
        for piece in (_split_long(p.strip()) if len(p.strip()) > LIMIT else [p.strip()])
    ]
    chunks, current = [], ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) > CHUNK_SIZE and current:
            chunks.append(current)
            current = current[-OVERLAP:] + "\n\n" + paragraph
        else:
            current = (current + "\n\n" + paragraph).strip()
    if current:
        chunks.append(current)
    return chunks


def main() -> None:
    count = 0
    with (
        (ROOT / "corpus.jsonl").open("w", encoding="utf-8") as output,
        (ROOT / "sources.csv").open(encoding="utf-8") as sources_file,
    ):
        for row in csv.DictReader(sources_file):
            text = (ROOT / "sources" / row["archivo"]).read_text(encoding="utf-8")
            for position, chunk in enumerate(split_text(text)):
                output.write(
                    json.dumps(
                        {
                            "id": f"{row['archivo']}#{position}",
                            "fuente": row["fuente"],
                            "url": row.get("url") or None,
                            "tipo": row.get("tipo") or None,
                            "sitio_id": row.get("sitio_id") or None,
                            "analogo_id": row.get("analogo_id") or None,
                            "texto": chunk,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                count += 1
    print(f"{count} fragmentos escritos en {ROOT / 'corpus.jsonl'} / fragments written")


if __name__ == "__main__":
    main()
