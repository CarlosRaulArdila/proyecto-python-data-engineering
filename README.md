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
- Logging and Error Handling: Maintains execution logs and pipeline error information.


Project Structure

proyecto_python_data_engineering/
│
├── config/
│   └── config.yaml
│
├── dags/
│   └── hospital_etl_dag.py
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── rejected/
│
├── docs/
│   ├── README.md
│   ├── arquitectura.md
│   ├── modulos.md
│   ├── configuracion.md
│   ├── despliegue.md
│   └── operacion.md
│
├── logs/
├── src/
├── tests/
│
├── .dockerignore
├── .env
├── .gitignore
├── Dockerfile
├── ejecutar_pipeline.bat
├── pytest.ini
├── README.md
└── requirements.txt


Installation and Local Development
1. Clone the repository

git clone https://github.com/CarlosRaulArdila/proyecto-python-data-engineering.git
cd proyecto-python-data-engineering


2. Create the Python environment
conda create -n data_engineering python=3.12
conda activate data_engineering

3. Install dependencies

pip install -r requirements.txt


4. Configure environment variables
Create a .env file in the project root with the database connection settings required by the local execution configuration.

Example:

DB_HOST=localhost
DB_PORT=5434
DB_NAME=hospital_dw
DB_USER=your_username
DB_PASSWORD=your_password


Replace the example values with the credentials and connection settings of your environment.

Never commit .env or expose database credentials.


5. Generate synthetic data

python src/generar_datos.py

6. Create the database table

python src/crear_tabla.py

7. Execute the pipeline locally

python src/ejecutar_pipeline.py

The local execution requires a running PostgreSQL instance, the target database, and valid environment variables.
Docker and Airflow Execution
The project includes a Docker image for executing the ETL application:

docker build -t hospital-etl:1.0 .

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

The validated test suite currently contains 22 passing tests.
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
Automated tests passed	22

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


Project version: 1.0.0
Status: Core ETL, incremental loading, Docker execution, Airflow orchestration, auditing, and automated tests validated.
