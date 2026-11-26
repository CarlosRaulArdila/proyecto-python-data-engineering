FROM python:3.12-slim

ARG ETL_VERSION=2.0.0

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
COPY --chown=etl:etl pipelines/ ./pipelines/

RUN mkdir -p data/raw data/processed data/rejected logs \
    && chown -R etl:etl /app

USER etl

# Comando por defecto: pipeline completo (config/config.yaml).
# Migraciones: docker run ... hospital-etl:<version> python -m src.migrar
# Otro pipeline: docker run -e ETL_CONFIG_PATH=pipelines/ventas/config.yaml ...
CMD ["python", "-m", "src.ejecutar_pipeline"]
