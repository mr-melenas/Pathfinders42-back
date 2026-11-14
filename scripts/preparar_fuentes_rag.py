"""Prepara las fuentes del corpus del RAG: data/rag/sources/*.md y data/rag/sources.csv.

Entradas (versionadas en el repo):
- scripts/entrada/rag/*.md: notas escritas a mano (límites de la Tierra como análogo y resumen del método
  de cada capa), con una cabecera `fuente`, `url` y `tipo`.
- scripts/entrada/ficha_analogos.csv: copia de la Google Sheet «ficha_analogos» (pestaña Fichas). Cada
  lugar con rasgo análogo da un archivo (tipo `ficha`, con su `analogo_id`).
- docs/usos.md, docs/m1_buscador_analogos.md y SOURCES.md, sin las secciones de API ni de cómo regenerar.

Después: python scripts/build_corpus.py (corpus.jsonl) y python scripts/generate_explanations.py.
Uso: python scripts/preparar_fuentes_rag.py
"""

import csv
import re
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "scripts" / "entrada"
DESTINO = RAIZ / "data" / "rag"
REPO = "https://github.com/mr-melenas/Pathfinders42-back/blob/main"

# Documentos del repo que entran en el corpus, y secciones que se quitan (no son contenido científico)
DOCS = {
    "docs/usos.md": ("Pathfinders42 · Usos de misión (enfoque D)", "metodo"),
    "docs/m1_buscador_analogos.md": ("Pathfinders42 · M1, buscador de análogos nuevos", "metodo"),
    "SOURCES.md": ("Pathfinders42 · Fuentes de datos y licencias", "fuentes"),
}
SECCIONES_FUERA = re.compile(r"api|regenerar|reentrenar|siguientes pasos|glosario", re.IGNORECASE)
CAMPOS_FICHA = [
    ("País o región", "pais"),
    ("Perfil (a qué se parece)", "perfil"),
    ("Verificación", "verificacion"),
    ("Rasgo análogo", "rasgo_analogo"),
    ("Tipo geológico", "tipo_geologico"),
    ("Proyectos y agencias", "proyectos_agencias"),
    ("Datos publicados", "fuente_datos_publicados"),
    ("Accesibilidad", "accesibilidad"),
    ("Referencia principal", "referencia_principal"),
    ("Notas", "notas"),
]


def leer_nota(ruta: Path) -> tuple[dict[str, str], str]:
    """Cabecera `clave: valor` entre líneas `---` y el cuerpo de la nota."""
    texto = ruta.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n(.*)", texto, re.S)
    if not m:
        raise SystemExit(f"{ruta.name}: falta la cabecera --- fuente/url/tipo ---")
    meta = dict(linea.split(": ", 1) for linea in m.group(1).splitlines() if ": " in linea)
    return meta, m.group(2).strip() + "\n"


def sin_secciones(texto: str) -> str:
    """Quita las secciones ## cuyo título es de API, regenerar, etc. (con sus subsecciones)."""
    salida, fuera = [], False
    for linea in texto.splitlines():
        if linea.startswith("## "):
            fuera = bool(SECCIONES_FUERA.search(linea))
        if not fuera:
            salida.append(linea)
    return "\n".join(salida).strip() + "\n"


def ficha_md(r: dict[str, str]) -> str:
    lineas = [f"# {r['nombre']} (análogo terrestre)", ""]
    if r.get("lat") and r.get("lon"):
        nota = f" ({r['coord_nota']})" if r.get("coord_nota") else ""
        lineas.append(f"- Coordenadas: {r['lat']}, {r['lon']}{nota}")
    for etiqueta, campo in CAMPOS_FICHA:
        if r.get(campo, "").strip():
            lineas.append(f"- {etiqueta}: {r[campo].strip()}")
    urls = [r[k] for k in ("url_1", "url_2") if r.get(k, "").startswith("http")]
    if urls:
        lineas.append(f"- Enlaces: {' ; '.join(urls)}")
    return "\n".join(lineas) + "\n"


def main() -> None:
    fuentes = DESTINO / "sources"
    if fuentes.exists():
        shutil.rmtree(fuentes)
    fuentes.mkdir(parents=True)
    filas = []

    def guardar(nombre: str, texto: str, fuente: str, url: str, tipo: str, analogo_id: str = "") -> None:
        (fuentes / nombre).write_text(texto, encoding="utf-8")
        filas.append(
            {
                "archivo": nombre,
                "fuente": fuente,
                "url": url,
                "tipo": tipo,
                "sitio_id": "",
                "analogo_id": analogo_id,
            }
        )

    for ruta in sorted((ENTRADA / "rag").glob("*.md")):
        meta, cuerpo = leer_nota(ruta)
        guardar(ruta.name, cuerpo, meta["fuente"], meta.get("url", f"{REPO}/README.md"), meta["tipo"])

    with (ENTRADA / "ficha_analogos.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("rasgo_analogo", "").strip():  # filas sin investigar (solo un nombre)
                continue
            fuente = f"Ficha de análogos · {r['nombre']}"
            if r.get("referencia_principal"):
                fuente += f" ({r['referencia_principal'].strip()})"
            url = r.get("url_1") if r.get("url_1", "").startswith("http") else ""
            guardar(f"ficha_{r['id']}.md", ficha_md(r), fuente, url, "ficha", r["id"])

    for rel, (fuente, tipo) in DOCS.items():
        texto = sin_secciones((RAIZ / rel).read_text(encoding="utf-8"))
        guardar(Path(rel).name, texto, fuente, f"{REPO}/{rel}", tipo)

    with (DESTINO / "sources.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["archivo", "fuente", "url", "tipo", "sitio_id", "analogo_id"])
        w.writeheader()
        w.writerows(filas)
    por_tipo: dict[str, int] = {}
    for fila in filas:
        por_tipo[fila["tipo"]] = por_tipo.get(fila["tipo"], 0) + 1
    print(f"{len(filas)} fuentes en {fuentes}: {por_tipo}")


if __name__ == "__main__":
    main()
