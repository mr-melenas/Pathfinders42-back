FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install .

# Los datos sincronizados (data/06_web) se copian si existen en el contexto de build
COPY data ./data

RUN useradd --create-home api && chown -R api /srv
USER api

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
