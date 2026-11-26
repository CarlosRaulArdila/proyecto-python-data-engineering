"""
Conexión a PostgreSQL.

El motor (engine) se crea de forma perezosa: importar este módulo
no exige credenciales ni abre conexiones. Así los tests unitarios
y las herramientas que solo importan código funcionan sin `.env`.

Prioridad de las credenciales:
1. Variables de entorno del proceso (Airflow, Docker, CI).
2. Archivo `.env` en la raíz del proyecto (desarrollo local).
"""

import logging
import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine

from src.configuracion import BASE_DIR

logger = logging.getLogger(__name__)

# override=False: las variables ya definidas en el entorno
# (por ejemplo, las que inyecta Airflow) tienen prioridad sobre .env
load_dotenv(BASE_DIR / ".env", override=False)

VARIABLES_REQUERIDAS = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
)

_engine: Engine | None = None


def construir_url() -> URL:
    """Construye la URL de conexión a partir de las variables de entorno."""

    valores = {nombre: os.getenv(nombre) for nombre in VARIABLES_REQUERIDAS}
    faltantes = [nombre for nombre, valor in valores.items() if not valor]

    if faltantes:
        raise ValueError(
            "Faltan variables de conexión a PostgreSQL: "
            + ", ".join(faltantes)
            + ". Defínalas en el entorno o en el archivo .env "
            "(ver .env.example)."
        )

    return URL.create(
        drivername="postgresql+psycopg2",
        username=valores["DB_USER"],
        password=valores["DB_PASSWORD"],
        host=valores["DB_HOST"],
        port=int(valores["DB_PORT"]),
        database=valores["DB_NAME"],
    )


def obtener_engine() -> Engine:
    """Devuelve un único engine por proceso, creándolo en la primera llamada."""

    global _engine

    if _engine is None:
        _engine = create_engine(
            construir_url(),
            pool_pre_ping=True,
            connect_args={
                "application_name": os.getenv(
                    "ETL_PIPELINE_ID", "proyecto_python_data_engineering"
                )
            },
        )

    return _engine


def cerrar_engine() -> None:
    """Libera las conexiones del pool (útil al final de un proceso o en tests)."""

    global _engine

    if _engine is not None:
        _engine.dispose()
        _engine = None


def probar_conexion() -> bool:
    """Comprueba la conexión e informa la versión de PostgreSQL."""

    try:
        engine = obtener_engine()

        with engine.connect() as conexion:
            version = conexion.execute(text("SELECT version()")).scalar()

        logger.info("Conexión exitosa | Base de datos: %s", engine.url.database)
        logger.info("PostgreSQL: %s", version)
        return True

    except Exception:
        logger.exception("Error de conexión a PostgreSQL")
        return False


if __name__ == "__main__":
    from src.registro_logs import configurar_logging

    configurar_logging()
    raise SystemExit(0 if probar_conexion() else 1)
