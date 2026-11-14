"""Copia 06_web (exportado por los notebooks de Colab) a data/06_web y escribe data/VERSION.json.

Uso:
    python scripts/sync_data.py --origen "/ruta/a/Hackathon Nasa/06_web"

En Colab el origen es /content/drive/MyDrive/Hackathon Nasa/06_web; en local, la carpeta
de Google Drive para escritorio o una copia descargada.

Al terminar vuelve a construir las capas que se generan en el repo y no vienen de Drive (ahora, `usos`
con scripts/construir_usos.py): la copia las borra y, además, dependen de los datos recién copiados.
Para saltarlo: --sin-usos.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
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


def reconstruir_usos(destino: Path) -> None:
    """Capa usos_v0: se calcula en el repo a partir de las capas copiadas (ver scripts/construir_usos.py)."""
    script = RAIZ / "scripts" / "construir_usos.py"
    subprocess.run([sys.executable, str(script), "--web", str(destino)], check=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--origen", required=True, type=Path, help="Carpeta 06_web de Drive")
    p.add_argument("--destino", type=Path, default=RAIZ / "data" / "06_web", help="Por defecto, data/06_web")
    p.add_argument("--sin-usos", action="store_true", help="No volver a construir la capa usos")
    args = p.parse_args()
    destino = args.destino.resolve()
    version = sincronizar(args.origen.expanduser().resolve(), destino)
    print(f"✅ {version['archivos']} archivos, {version['bytes'] / 1024**2:.1f} MB, hash {version['hash']}")
    if not args.sin_usos:
        reconstruir_usos(destino)


if __name__ == "__main__":
    main()
