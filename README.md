# Hospital Data Engineering ETL Pipeline

A modular and reusable end-to-end Data Engineering project designed to consolidate, clean, validate, and incrementally load hospital data using Python, PostgreSQL, Docker, and Apache Airflow.

The project includes data quality controls, automated testing, incremental UPSERT operations, execution auditing, logging, containerization, and workflow orchestration.

## Project Overview

The pipeline processes data from multiple hospital CSV sources and loads validated records into a PostgreSQL data warehouse.

Its architecture separates data processing, orchestration, persistence, and execution auditing to facilitate maintenance, scalability, and reuse in other data engineering projects.

## Architecture

```mermaid
flowchart TD
    A["Hospital CSV Sources"] --> B["Raw Data"]
    B --> C["Data Consolidation"]
    C --> D["Data Cleaning"]
    D --> E["Data Validation"]
    E --> F["Processed and Rejected Data"]
    F --> G["Incremental Loading"]
    G --> H[("PostgreSQL Data Warehouse")]

    I["Apache Airflow"] --> J["DockerOperator"]
    J --> K["ETL Docker Container"]
    K --> C
    K --> D
    K --> E
    K --> G

    K --> L["Execution Audit"]
    L --> H

Technology Stack
Technology	Purpose
Python 3.12	ETL development
Pandas	Data transformation
SQLAlchemy	Database connectivity
PostgreSQL 16	Data warehouse and audit storage
Docker	ETL containerization
Apache Airflow 2.10.3	Workflow orchestration
Pytest	Automated testing
Conda	Python environment management
Git	Version control


Key Features
- Data Generation: Creates synthetic hospital datasets for development and testing.
- Data Consolidation: Combines multiple CSV sources into a unified dataset.
- Data Cleaning: Identifies incomplete and duplicate records.
- Data Validation: Applies predefined business rules.
- Incremental Loading: Uses PostgreSQL UPSERT operations to insert or update records.
- Idempotency: Prevents unnecessary database operations when source data has not changed.
- Automated Testing: Includes unit and integration-oriented tests using Pytest.
- Containerization: Packages the ETL application in a Docker image.
- Workflow Orchestration: Executes the ETL pipeline through Apache Airflow and DockerOperator.
- Execution Auditing: Stores execution metadata, metrics, duration, status, and error information in PostgreSQL.
- Logging and Error Handling: Console and rotating file logs, with the execution `run_id` on every line.
- Versioned Database Migrations: `sql/migraciones/` applied by `python -m src.migrar`, tracked in `public.etl_migraciones` with checksums.
- Business-Key Conflict Detection: Records sharing `(numero_historia, fecha, hospital_origen)` with different values are quarantined instead of loaded arbitrarily.
- Config-Driven Stages: Pipeline stages are declared in `config.yaml` (module + function) and return their metrics directly; no subprocess output parsing.
- Reproducible Local Environment: `docker-compose.yml` with a PostgreSQL warehouse, migrations and the ETL engine.
- Continuous Integration: GitHub Actions runs Ruff, unit tests with coverage, PostgreSQL integration tests and the Docker build.

Reusable template (v2.0.0)
The engine in `src/` contains nothing specific to hospitals. Each pipeline is defined only by configuration:
- Data contract (`esquema`): columns, types, required fields, max length, derived columns.
- Declarative business rules (`reglas`): `rango`, `valores_permitidos`, `patron`, each with its rejection message. Vectorized validation (200,000 rows in ~0.4 s).
- Business key and UPSERT generated from the configuration, with a pre-check of the target table.
- File patterns per source (batches), `completa` or `incremental` ingestion (SHA-256 based) and file lineage in `etl_archivos_procesados`.
- One PostgreSQL schema per project, with its own migrations, audit and lineage tables.
- Example: `pipelines/ventas/` — a retail sales pipeline built with zero new Python code. See `docs/nuevo_pipeline.md`.

Operations (v2.1.0): data-quality thresholds that stop the load, rejection history in the
database, e-mail/webhook alerts, an Airflow DAG factory with per-pipeline schedules, and an
operations dashboard (`python -m src.tablero`) built on SQL views ready for Power BI.

Run another pipeline by pointing to its configuration:

ETL_CONFIG_PATH=pipelines/ventas/config.yaml python -m src.migrar
ETL_CONFIG_PATH=pipelines/ventas/config.yaml python -m src.ejecutar_pipeline


Project Structure

proyecto_python_data_engineering/
│
├── config/
│   └── config.yaml
│
├── .github/workflows/
│   └── ci.yml
│
├── dags/
│   ├── fabrica_pipelines_etl.py   # DAG factory: one DAG per pipeline config
│   └── etl_fabrica_config.py      # factory logic (no Airflow imports, unit-tested)
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── rejected/
│
├── pipelines/
│   └── ventas/             # example pipeline: config.yaml, migrations, sample data
│
├── docs/
│   ├── README.md
│   ├── nuevo_pipeline.md
│   ├── arquitectura.md
│   ├── modulos.md
│   ├── configuracion.md
│   ├── despliegue.md
│   └── operacion.md
│
├── logs/
├── sql/
│   └── migraciones/        # V001__..., V002__..., V003__...
├── src/
├── tests/
│   ├── datos/              # sample CSV fixtures
│   └── integracion/        # PostgreSQL end-to-end tests
│
├── .dockerignore
├── .env                    # local only, never committed
├── .env.example
├── .gitignore
├── CHANGELOG.md
├── docker-compose.yml
├── Dockerfile
├── ejecutar_pipeline.bat
├── pytest.ini
├── README.md
├── requirements.txt
├── requirements-dev.txt
└── ruff.toml


Installation and Local Development
1. Clone the repository

git clone https://github.com/CarlosRaulArdila/proyecto-python-data-engineering.git
cd proyecto-python-data-engineering


2. Create the Python environment
conda create -n data_engineering python=3.12
conda activate data_engineering

3. Install dependencies

pip install -r requirements-dev.txt   # includes requirements.txt + pytest + ruff


4. Configure environment variables
Copy the template and replace the values:

cp .env.example .env

Main variables:

DB_HOST=localhost
DB_PORT=5434
DB_NAME=hospital_dw
DB_USER=your_username
DB_PASSWORD=your_password


Replace the example values with the credentials and connection settings of your environment.

Never commit .env or expose database credentials.


5. Generate synthetic data

python -m src.generar_datos

6. Apply the database migrations (idempotent)

python -m src.migrar

7. Execute the pipeline locally

python -m src.ejecutar_pipeline

All modules are run from the project root with `python -m src.<module>`.

The local execution requires a running PostgreSQL instance, the target database, and valid environment variables.

Alternative: self-contained Docker Compose environment

docker compose up -d warehouse
docker compose run --rm migraciones
docker compose run --rm etl

The compose warehouse listens on host port 5435 by default (`WAREHOUSE_PORT`) to avoid clashing with the Airflow warehouse on 5434.
Docker and Airflow Execution
The project includes a Docker image for executing the ETL application:

docker build --build-arg ETL_VERSION=2.1.0 -t hospital-etl:2.1.0 .

The Airflow DAG factory (`dags/fabrica_pipelines_etl.py`) creates one DAG per pipeline config; each runs `aplicar_migraciones` >> `ejecutar_pipeline_etl` with this image. Rebuild the image after updating the code.

The Airflow environment is maintained separately and uses Docker Compose.

To start the Airflow environment:

cd ~/airflow-docker
docker compose up -d

The main DAG is:

hospital_etl_pipeline

To trigger it manually:

docker compose exec scheduler airflow dags trigger hospital_etl_pipeline

Airflow Web UI:

http://localhost:8080

For detailed deployment instructions, see Deployment Documentation.
Testing
Run the automated test suite:

pytest -v

Lint:

ruff check .

Integration tests (require a disposable PostgreSQL database whose name ends in `_test`; they drop and recreate the project tables):

RUN_INTEGRATION_TESTS=1 DB_NAME=hospital_dw_test pytest -v -m integracion

The suite contains 237 unit tests and 11 PostgreSQL integration tests (migrations from v1.0, full load + idempotent rerun + update, audited failure, file lineage, incremental batches, no registration on failure, and the full sales pipeline).
Validated Execution Results
The initial synthetic dataset contains 15 records from three hospital sources.
Metric	Result
Source hospitals	3
Initial records	15
Clean records	12
Rejected records	3
Incomplete records rejected	2
Duplicate records rejected	1
Database operations on unchanged rerun	0
Automated tests passed	248 (237 unit + 11 integration)

The integrated execution through Apache Airflow and Docker has been validated successfully.

A repeated execution without source changes can complete successfully with zero database operations, demonstrating the idempotent behavior of the incremental loading process.

Execution Auditing
Every pipeline execution is registered in:

public.etl_auditoria

The audit table stores:
- Execution identifier (run_id).
- Project and pipeline identifiers.
- Orchestrator and pipeline version.
- Execution environment.
- Start and end timestamps.
- Execution status and duration.
- Extracted, clean, and rejected record counts.
- Database operations.
- Log file reference and error information.

Documentation
Detailed technical documentation is available in the docs/ directory.
Document	Description
Architecture	System architecture and data flow
Modules	Python module inventory
Configuration	Configuration and environment variables
Deployment	Docker and Airflow deployment
Operations	Execution, monitoring, auditing, and maintenance


Reusability
This project is designed as a reusable foundation for other ETL initiatives.

To adapt it to a new project, configure:
1. Data sources and input formats.
2. Data cleaning and validation rules.
3. PostgreSQL database and destination tables.
4. Environment variables and database connections.
5. Docker image and volume mappings.
6. Airflow DAG identifiers and orchestration settings.
7. Project and pipeline metadata.


Future Improvements
- Cloud deployment and integration.
- Advanced data quality monitoring.
- Automated scheduling and operational alerting.
- Support for additional data sources and formats.
- Expanded integration and end-to-end testing.
- Infrastructure and deployment automation.


Project version: 2.1.0
Status: Phase 3 (autonomous operation) completed: quality thresholds, rejection history, e-mail/webhook alerts, Airflow DAG factory with schedules, operations views and dashboard. See CHANGELOG.md.
