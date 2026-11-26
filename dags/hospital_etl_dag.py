"""
DAG de Airflow del pipeline ETL hospitalario.

Flujo:
    aplicar_migraciones  >>  ejecutar_pipeline_etl

Ambas tareas usan la misma imagen Docker del motor ETL. Los valores
específicos del entorno se leen de variables de entorno del scheduler
(con valores por defecto para el entorno local actual), de modo que
el archivo no necesita editarse al cambiar de máquina o de proyecto.

Variables de entorno admitidas (definirlas en el docker-compose de Airflow):
    ETL_PROJECT_PATH     Ruta del proyecto en el host Docker
    ETL_IMAGE            Imagen del motor ETL (con etiqueta de versión)
    ETL_DOCKER_NETWORK   Red Docker compartida con el warehouse
    ETL_AIRFLOW_CONN_ID  Conexión de Airflow con las credenciales del warehouse
    ETL_ENVIRONMENT      Ambiente (desarrollo, qa, produccion)
"""

import os
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

# --------------------------------------------------
# CONFIGURACION GENERAL
# --------------------------------------------------

PIPELINE_VERSION = "2.0.0"

PROJECT_PATH = os.getenv(
    "ETL_PROJECT_PATH",
    "/mnt/c/Users/User/Documents/proyecto_python_data_engineering",
)

IMAGEN_ETL = os.getenv("ETL_IMAGE", f"hospital-etl:{PIPELINE_VERSION}")
DOCKER_NETWORK = os.getenv("ETL_DOCKER_NETWORK", "airflow-docker_default")
CONN_ID = os.getenv("ETL_AIRFLOW_CONN_ID", "hospital_dw_etl")
AMBIENTE = os.getenv("ETL_ENVIRONMENT", "desarrollo")


# Credenciales obtenidas de la conexión cifrada de Airflow
ENTORNO_BD = {
    "DB_HOST": f"{{{{ conn.{CONN_ID}.host }}}}",
    "DB_PORT": f"{{{{ conn.{CONN_ID}.port }}}}",
    "DB_NAME": f"{{{{ conn.{CONN_ID}.schema }}}}",
    "DB_USER": f"{{{{ conn.{CONN_ID}.login }}}}",
    "DB_PASSWORD": f"{{{{ conn.{CONN_ID}.password }}}}",
}

ENTORNO_EJECUCION = {
    "ETL_ORCHESTRATOR": "airflow",
    "ETL_PIPELINE_ID": "{{ dag.dag_id }}",
    "ETL_PIPELINE_VERSION": PIPELINE_VERSION,
    "ETL_ENVIRONMENT": AMBIENTE,
}

MONTAJES_DATOS = [
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
]

# Parámetros comunes a todas las tareas Docker
PARAMETROS_DOCKER = {
    "image": IMAGEN_ETL,
    "docker_url": "unix://var/run/docker.sock",
    "docker_conn_id": None,
    "network_mode": DOCKER_NETWORK,
    "auto_remove": "success",
    "mount_tmp_dir": False,
    "force_pull": False,
}


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
    default_args={
        "owner": "data-engineering",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["data-engineering", "hospital", "etl", "docker"],
) as dag:

    aplicar_migraciones = DockerOperator(
        task_id="aplicar_migraciones",
        command=["python", "-m", "src.migrar"],
        environment={**ENTORNO_BD, **ENTORNO_EJECUCION},
        execution_timeout=timedelta(minutes=5),
        **PARAMETROS_DOCKER,
    )

    ejecutar_pipeline = DockerOperator(
        task_id="ejecutar_pipeline_etl",
        command=["python", "-m", "src.ejecutar_pipeline"],
        mounts=MONTAJES_DATOS,
        environment={**ENTORNO_BD, **ENTORNO_EJECUCION},
        execution_timeout=timedelta(minutes=15),
        **PARAMETROS_DOCKER,
    )

    aplicar_migraciones >> ejecutar_pipeline
