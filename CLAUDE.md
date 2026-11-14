# CLAUDE.md

Backend (FastAPI) del proyecto Pathfinders42 · NASA Space Apps Challenge 2026: análogos terrestres de la
Luna y Marte. El equipo habla español: código, docs, commits y PR en español.

## Decisiones que no hay que reabrir
- La API **solo sirve resultados precalculados** de `data/06_web` (copia de `06_web` de Drive, generada por
  los notebooks de Colab). Nada de cálculos pesados ni modelos en el servidor.
- Punto de entrada de los datos: `data/06_web/manifest.json` (`capas`, `cuerpos`). Las rutas a archivos
  salen siempre del manifest y pasan por `Datos.ruta_segura` (no salir de la carpeta de datos).
- Sin base de datos para los datos científicos. Supabase (Postgres + pgvector) solo para el asistente.
- El OpenAPI que genera FastAPI es el contrato con el front (`openapi-typescript`). Todo endpoint lleva
  `response_model` o `responses` documentados.
- Prefijo `/api/v1`. Un router por grupo en `app/routers/`. Dependencia de datos: `DatosDep`.

## Ramas
- Las ramas de trabajo (`feat/…`, `fix/…`) salen de `dev` y sus PR van a `dev`, nunca a `main`.
- `main` solo recibe PR `dev → main` cuando dev está probado. Nada de push directo a `main` ni a `dev`.

## Comandos
- Tests: `pytest` (usan `tests/fixtures/06_web`, no los datos reales).
- Lint: `ruff check . && ruff format --check .` (CI lo exige).
- Local: `uvicorn app.main:app --reload`.

## Plan
Endpoints previstos y sprints: ver el plan de desarrollo en la Hoja de ruta del equipo y el GitHub Project
(vista «Sprint actual», campos Prioridad y Sprint).
