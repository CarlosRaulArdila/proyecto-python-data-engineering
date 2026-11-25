
from datetime import timedelta

import pendulum

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount


# --------------------------------------------------
# CONFIGURACION GENERAL
# --------------------------------------------------

PROJECT_PATH = (
    "/mnt/c/Users/User/Documents/"
    "proyecto_python_data_engineering"
)

DOCKER_NETWORK = "airflow-docker_default"


# --------------------------------------------------
# DEFINICION DEL DAG
# --------------------------------------------------

with DAG(
    dag_id="hospital_etl_pipeline",
    description="Pipeline modular de Ingenieria de Datos Hospitalarios",
    start_date=pendulum.datetime(2026, 11, 23, tz="America/Bogota"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["data-engineering", "hospital", "etl", "docker"],
) as dag:

    ejecutar_pipeline = DockerOperator(
        task_id="ejecutar_pipeline_etl",

        # Imagen Docker del motor ETL
        image="hospital-etl:1.0",

        # Comunicacion con Docker
        docker_url="unix://var/run/docker.sock",
        docker_conn_id=None,
        network_mode=DOCKER_NETWORK,

        # Montaje de directorios
        mounts=[
            Mount(
                source=f"{PROJECT_PATH}/data/raw",
                target="/app/data/raw",
                type="bind",
                read_only=True,
            ),
            Mount(
                source=f"{PROJECT_PATH}/data/processed",
                target="/app/data/processed",
                type="bind",
            ),
            Mount(
                source=f"{PROJECT_PATH}/data/rejected",
                target="/app/data/rejected",
                type="bind",
            ),
            Mount(
                source=f"{PROJECT_PATH}/logs",
                target="/app/logs",
                type="bind",
            ),
        ],

        # Credenciales obtenidas de la conexion cifrada de Airflow
        environment={
            "DB_HOST": "{{ conn.hospital_dw_etl.host }}",
            "DB_PORT": "{{ conn.hospital_dw_etl.port }}",
            "DB_NAME": "{{ conn.hospital_dw_etl.schema }}",
            "DB_USER": "{{ conn.hospital_dw_etl.login }}",
            "DB_PASSWORD": "{{ conn.hospital_dw_etl.password }}",

            "ETL_ORCHESTRATOR": "airflow",
            "ETL_PIPELINE_ID": "{{ dag.dag_id }}",
            "ETL_PIPELINE_VERSION": "1.0.0",
            "ETL_ENVIRONMENT": "desarrollo",
        },

        # Comportamiento del contenedor
        auto_remove="success",
        mount_tmp_dir=False,
        force_pull=False,
        execution_timeout=timedelta(minutes=15),
    )
