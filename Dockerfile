FROM python:3.12-slim

ARG ETL_VERSION=1.1.0

LABEL org.opencontainers.image.title="hospital-etl" \
      org.opencontainers.image.version="${ETL_VERSION}" \
      org.opencontainers.image.description="Motor ETL modular: consolidación, limpieza, validación y carga incremental en PostgreSQL"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ETL_PIPELINE_VERSION=${ETL_VERSION}

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system etl \
    && useradd --system --gid etl --create-home --home-dir /home/etl etl

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY --chown=etl:etl src/ ./src/
COPY --chown=etl:etl config/ ./config/
COPY --chown=etl:etl sql/ ./sql/

RUN mkdir -p data/raw data/processed data/rejected logs \
    && chown -R etl:etl /app

USER etl

# Comando por defecto: pipeline completo.
# Migraciones: docker run ... hospital-etl:<version> python -m src.migrar
CMD ["python", "-m", "src.ejecutar_pipeline"]
