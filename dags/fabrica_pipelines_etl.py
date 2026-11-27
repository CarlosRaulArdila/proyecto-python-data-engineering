"""
Fábrica de DAG: crea un DAG de Airflow por cada pipeline del proyecto.

- Descubre config/config.yaml y pipelines/<nombre>/config.yaml (montados
  en el scheduler en ETL_CONFIGS_DIR, por defecto /opt/airflow/proyecto_etl).
- Cada DAG ejecuta, con la imagen del motor ETL:
      aplicar_migraciones  >>  ejecutar_pipeline_etl
- Horario, zona horaria, reintentos y conexión se leen de la sección
  `orquestacion` de cada config.yaml (ver etl_fabrica_config.py).

Para agregar un pipeline nuevo no hay que escribir ningún DAG: basta con
crear pipelines/<nombre>/config.yaml y reconstruir la imagen ETL.

Variables de entorno del scheduler (opcionales):
    ETL_CONFIGS_DIR     Carpeta con config/ y pipelines/ (montada en solo lectura)
    ETL_PROJECT_PATH    Ruta del proyecto en el host Docker (para montar data/ y logs/)
    ETL_IMAGE           Imagen del motor ETL
    ETL_DOCKER_NETWORK  Red Docker compartida con el warehouse

Variables de Airflow para las alertas (opcionales; si no existen, no hay correo):
    ETL_SMTP_HOST, ETL_SMTP_PUERTO, ETL_SMTP_USUARIO, ETL_SMTP_PASSWORD,
    ETL_ALERTA_DESTINATARIOS
"""

import logging
import os
import smtplib
import ssl
import sys
from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path

import pendulum
from airflow import DAG
from airflow.models import Variable
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

# El scheduler solo añade al sys.path la carpeta raíz de DAG; este archivo
# está en una subcarpeta, así que se añade la suya para importar el módulo vecino.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from etl_fabrica_config import (  # noqa: E402
    VERSION_MOTOR,
    EspecificacionDag,
    es_fallo_reportado_por_el_pipeline,
    especificaciones,
)

logger = logging.getLogger(__name__)

RAIZ_CONFIGS = Path(os.getenv("ETL_CONFIGS_DIR", "/opt/airflow/proyecto_etl"))
PROJECT_PATH = os.getenv(
    "ETL_PROJECT_PATH",
    "/mnt/c/Users/User/Documents/proyecto_python_data_engineering",
)
IMAGEN_ETL = os.getenv("ETL_IMAGE", f"hospital-etl:{VERSION_MOTOR}")
DOCKER_NETWORK = os.getenv("ETL_DOCKER_NETWORK", "airflow-docker_default")

# Secretos de correo desde Variables de Airflow (con valor por defecto vacío:
# si no están definidas, el pipeline simplemente omite el canal de correo).
ENTORNO_ALERTAS = {
    "ETL_SMTP_HOST": "{{ var.value.get('ETL_SMTP_HOST', '') }}",
    "ETL_SMTP_PUERTO": "{{ var.value.get('ETL_SMTP_PUERTO', '587') }}",
    "ETL_SMTP_USUARIO": "{{ var.value.get('ETL_SMTP_USUARIO', '') }}",
    "ETL_SMTP_CLAVE": "{{ var.value.get('ETL_SMTP_PASSWORD', '') }}",
    "ETL_ALERTA_DESTINATARIOS": "{{ var.value.get('ETL_ALERTA_DESTINATARIOS', '') }}",
}


def alertar_fallo_de_airflow(context) -> None:
    """
    Callback de fallo: avisa por correo cuando una tarea falla por un motivo
    que el pipeline no pudo reportar (imagen inexistente, contenedor que no
    arranca, tiempo agotado, migraciones...). Nunca lanza excepciones.
    """

    try:
        tarea = context["task_instance"]
        excepcion = context.get("exception")

        if es_fallo_reportado_por_el_pipeline(tarea.task_id, excepcion):
            return

        host = Variable.get("ETL_SMTP_HOST", default_var=None)
        usuario = Variable.get("ETL_SMTP_USUARIO", default_var=None)
        clave = Variable.get("ETL_SMTP_PASSWORD", default_var=None)
        destinatarios = Variable.get("ETL_ALERTA_DESTINATARIOS", default_var="")
        puerto = int(Variable.get("ETL_SMTP_PUERTO", default_var="587"))

        if not (host and usuario and clave and destinatarios):
            logger.warning("Variables ETL_SMTP_* no configuradas: no se envía la alerta.")
            return

        mensaje = EmailMessage()
        mensaje["Subject"] = f"[ETL] FALLO EN AIRFLOW - {tarea.dag_id}.{tarea.task_id}"
        mensaje["From"] = usuario
        mensaje["To"] = destinatarios
        mensaje.set_content(
            "La tarea falló antes de que el pipeline pudiera registrar su resultado.\n\n"
            f"DAG:       {tarea.dag_id}\n"
            f"Tarea:     {tarea.task_id}\n"
            f"Ejecución: {context.get('run_id')}\n"
            f"Intento:   {tarea.try_number}\n"
            f"Error:     {excepcion}\n\n"
            f"Log: {tarea.log_url}\n"
        )

        with smtplib.SMTP(host, puerto, timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(usuario, clave)
            smtp.send_message(mensaje)

    except Exception:
        logger.exception("No se pudo enviar la alerta de fallo de Airflow")


def crear_dag(spec: EspecificacionDag) -> DAG:
    entorno = {
        "DB_HOST": f"{{{{ conn.{spec.conexion_airflow}.host }}}}",
        "DB_PORT": f"{{{{ conn.{spec.conexion_airflow}.port }}}}",
        "DB_NAME": f"{{{{ conn.{spec.conexion_airflow}.schema }}}}",
        "DB_USER": f"{{{{ conn.{spec.conexion_airflow}.login }}}}",
        "DB_PASSWORD": f"{{{{ conn.{spec.conexion_airflow}.password }}}}",
        "ETL_CONFIG_PATH": spec.ruta_config,
        "ETL_ORCHESTRATOR": "airflow",
        "ETL_PIPELINE_VERSION": VERSION_MOTOR,
        "ETL_ENVIRONMENT": spec.ambiente,
        **ENTORNO_ALERTAS,
    }

    # data/ y logs/ completos (lectura y escritura); las carpetas raw, solo lectura
    montajes = [
        Mount(source=f"{PROJECT_PATH}/data", target="/app/data", type="bind"),
        Mount(source=f"{PROJECT_PATH}/logs", target="/app/logs", type="bind"),
    ] + [
        Mount(source=f"{PROJECT_PATH}/{raw}", target=f"/app/{raw}", type="bind", read_only=True)
        for raw in spec.rutas_raw
    ]

    comunes = {
        "image": IMAGEN_ETL,
        "docker_url": "unix://var/run/docker.sock",
        "docker_conn_id": None,
        "network_mode": DOCKER_NETWORK,
        "auto_remove": "success",
        "mount_tmp_dir": False,
        "force_pull": False,
        "environment": entorno,
    }

    with DAG(
        dag_id=spec.dag_id,
        description=spec.descripcion,
        start_date=pendulum.datetime(2026, 11, 26, tz=spec.zona_horaria),
        schedule=spec.horario,
        catchup=False,
        max_active_runs=1,
        default_args={
            "owner": "data-engineering",
            "on_failure_callback": alertar_fallo_de_airflow,
        },
        tags=["etl", "fabrica", *spec.etiquetas],
        doc_md=f"Generado por la fábrica desde `{spec.ruta_config}`.",
    ) as dag:
        aplicar_migraciones = DockerOperator(
            task_id="aplicar_migraciones",
            command=["python", "-m", "src.migrar"],
            retries=spec.reintentos_migraciones,
            retry_delay=timedelta(minutes=spec.minutos_entre_reintentos),
            execution_timeout=timedelta(minutes=5),
            **comunes,
        )

        # Sin reintentos automáticos: un FALLIDO del pipeline ya quedó auditado y
        # alertado, y en modo incremental los archivos se reintentan en la
        # siguiente ejecución programada.
        ejecutar_pipeline = DockerOperator(
            task_id="ejecutar_pipeline_etl",
            command=["python", "-m", "src.ejecutar_pipeline"],
            retries=0,
            mounts=montajes,
            execution_timeout=timedelta(minutes=spec.tiempo_maximo_minutos),
            **comunes,
        )

        aplicar_migraciones >> ejecutar_pipeline

    return dag


ESPECIFICACIONES, ERRORES = especificaciones(RAIZ_CONFIGS)

for _error in ERRORES:
    logger.error("Pipeline omitido por configuración inválida: %s", _error)

for _spec in ESPECIFICACIONES:
    globals()[_spec.dag_id] = crear_dag(_spec)
