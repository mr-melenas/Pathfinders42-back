from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import ajustes
from app.explanations.router import router as explanations_router
from app.routers import candidatos, capas, salud, sitios

PREFIJO = "/api/v1"

app = FastAPI(
    title="Pathfinders42 API",
    version=__version__,
    description=(
        "Análogos terrestres de las bases y lugares de aterrizaje de la Luna y Marte "
        "(NASA Space Apps Challenge 2026). Sirve resultados precalculados en Colab."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ajustes().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(salud.router, prefix=PREFIJO)
app.include_router(capas.router, prefix=PREFIJO)
app.include_router(sitios.router, prefix=PREFIJO)
app.include_router(candidatos.router, prefix=PREFIJO)
app.include_router(explanations_router, prefix=PREFIJO)
