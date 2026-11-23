FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copiar código y configuración del proyecto
COPY src/ ./src/
COPY config/ ./config/

# Crear directorios de trabajo
RUN mkdir -p data/raw data/processed data/rejected logs

# Ejecutar el pipeline
CMD ["python", "-m", "src.ejecutar_pipeline"]
