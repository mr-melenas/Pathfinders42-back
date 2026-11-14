"""Configuración por variables de entorno (ver .env.example)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _lista(valor: str) -> list[str]:
    return [v.strip() for v in valor.split(",") if v.strip()]


@dataclass(frozen=True)
class Ajustes:
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("DATA_DIR", RAIZ / "data" / "06_web")).resolve()
    )
    cors_origins: list[str] = field(
        default_factory=lambda: _lista(
            os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
        )
    )


def ajustes() -> Ajustes:
    return Ajustes()
