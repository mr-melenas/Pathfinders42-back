"""
ES: Genera data/rag/explanations.json a partir de la API (paso offline, tras la congelación de datos).
Uso: python scripts/generate_explanations.py [URL_BASE]   (por defecto http://localhost:8000/api/v1)
EN: Generates data/rag/explanations.json from the API (offline step, after the data freeze).
Usage: python scripts/generate_explanations.py [BASE_URL]   (default http://localhost:8000/api/v1)
"""

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.explanations.generator import explain_record  # noqa: E402
from app.explanations.index import TextIndex  # noqa: E402

BASE_URL = "http://localhost:8000/api/v1"
OUTPUT_PATH = Path("data/rag/explanations.json")


def main(
    base_url: str = BASE_URL,
    output_path: Path | str = OUTPUT_PATH,
    index: TextIndex | None = None,
) -> dict:
    if index is None:
        index = TextIndex()
    output_path = Path(output_path)
    response = httpx.get(f"{base_url}/sitios", timeout=30)
    response.raise_for_status()
    explanations = {}
    for site in response.json():
        rec_res = httpx.get(f"{base_url}/sitios/{site['id']}", timeout=30)
        rec_res.raise_for_status()
        record = rec_res.json()
        explanations[site["id"]] = explain_record(record, index)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(explanations, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(explanations)} explicaciones escritas en {output_path} / explanations written")
    return explanations


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else BASE_URL
    main(url)
