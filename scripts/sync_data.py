"""Copia 06_web (exportado por los notebooks de Colab) a data/06_web y escribe data/VERSION.json.

Uso:
    python scripts/sync_data.py --origen "/ruta/a/Hackathon Nasa/06_web"

En Colab el origen es /content/drive/MyDrive/Hackathon Nasa/06_web; en local, la carpeta
de Google Drive para escritorio o una copia descargada.
"""

import argparse
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LIMITE_MB = 50  # GitHub avisa a partir de 50 MB y rechaza archivos de más de 100 MB


def hash_carpeta(carpeta: Path) -> tuple[str, int, int]:
    h = hashlib.sha256()
    n = total = 0
    for ruta in sorted(p for p in carpeta.rglob("*") if p.is_file()):
        h.update(str(ruta.relative_to(carpeta)).encode())
        h.update(ruta.read_bytes())
        n += 1
        total += ruta.stat().st_size
    return h.hexdigest()[:16], n, total


def sincronizar(origen: Path, destino: Path) -> dict:
    if not (origen / "manifest.json").is_file():
        raise SystemExit(f"No hay manifest.json en {origen}: ¿es la carpeta 06_web?")
    grandes = [p for p in origen.rglob("*") if p.is_file() and p.stat().st_size > LIMITE_MB * 1024**2]
    if grandes:
        lista = "\n  ".join(f"{p.relative_to(origen)} ({p.stat().st_size / 1024**2:.0f} MB)" for p in grandes)
        print(f"⚠ Archivos de más de {LIMITE_MB} MB (no subirlos al repo):\n  {lista}", file=sys.stderr)
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(origen, destino, ignore=shutil.ignore_patterns(".*", "__pycache__", "*.tmp"))
    huella, n, total = hash_carpeta(destino)
    manifest = json.loads((destino / "manifest.json").read_text(encoding="utf-8"))
    version = {
        "sincronizado": datetime.now(UTC).isoformat(timespec="seconds"),
        "hash": huella,
        "archivos": n,
        "bytes": total,
        "manifest_version": manifest.get("version"),
        "manifest_generado": manifest.get("generado"),
    }
    (destino.parent / "VERSION.json").write_text(
        json.dumps(version, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return version


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--origen", required=True, type=Path, help="Carpeta 06_web de Drive")
    p.add_argument("--destino", type=Path, default=RAIZ / "data" / "06_web", help="Por defecto, data/06_web")
    args = p.parse_args()
    version = sincronizar(args.origen.expanduser().resolve(), args.destino.resolve())
    print(f"✅ {version['archivos']} archivos, {version['bytes'] / 1024**2:.1f} MB, hash {version['hash']}")


if __name__ == "__main__":
    main()
