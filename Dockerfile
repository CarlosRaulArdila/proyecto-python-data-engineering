FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system etl \
    && useradd --system --gid etl --create-home --home-dir /home/etl etl

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=etl:etl src/ ./src/
COPY --chown=etl:etl config/ ./config/

RUN mkdir -p data/raw data/processed data/rejected logs \
    && chown -R etl:etl /app

USER etl

CMD ["python", "-m", "src.ejecutar_pipeline"]
