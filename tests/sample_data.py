"""
ES: Datos de ejemplo compartidos. La ficha es la de Malapert Massif del contexto del equipo; el
corpus es texto de PRUEBA, no contenido científico del proyecto.
"""

SAMPLE_RECORD = {
    "id": "artemis-malapert-massif",
    "nombre": "Malapert Massif",
    "cuerpo": "luna",
    "propiedades": {"fuente": "USGS ScienceBase", "url_fuente": "https://www.sciencebase.gov/"},
    "resumen": [
        {
            "capa": "anortosita",
            "descripcion": "Afloramientos de anortosita",
            "hay_parecido": True,
            "n_parejas": 3,
            "mejor": {
                "id": "lofoten_flakstadoy",
                "nombre": "Lofoten (macizo de Flakstadøy), Noruega",
                "distancia": 0.229,
                "parecido": True,
                "detalles": {"verificacion": "verificada", "d_geo": 0.3, "d_topo": 0.158},
            },
        },
        {
            "capa": "clima",
            "hay_parecido": False,
            "n_parejas": 5,
            "mejor": {
                "id": "analogo-luna-askja-islandia",
                "nombre": "Askja, Islandia",
                "distancia": 0.37,
                "parecido": None,
                "detalles": {"dist_clima": 0.082, "brecha_ts_media": -121.7, "brecha_ts_min": -188.2},
            },
        },
        {"capa": "cuevas", "hay_parecido": None, "n_parejas": 0, "mejor": None},
    ],
}

TEST_CORPUS = [
    {
        "id": "t#0",
        "fuente": "Fuente de prueba",
        "url": None,
        "tipo": "limites",
        "sitio_id": None,
        "texto": "Nota de prueba sobre la gravedad y la atmósfera como límite del análogo.",
    },
    {
        "id": "t#1",
        "fuente": "Otra fuente",
        "url": "https://example.org/b",
        "tipo": "paper",
        "sitio_id": "otro-sitio",
        "texto": "Texto de prueba sobre cuevas.",
    },
    {
        "id": "t#2",
        "fuente": "Otra fuente",
        "url": "https://example.org/b",
        "tipo": "paper",
        "sitio_id": None,
        "texto": "Segundo fragmento de prueba sobre cuevas lunares y tubos de lava.",
    },
]
