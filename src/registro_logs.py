"""
Configuración centralizada del sistema de logs.

- Un único punto de configuración (antes se configuraba al importar
  ejecutar_pipeline.py).
- Salida a consola (la recoge Docker/Airflow) y a archivo rotativo.
- Cada línea incluye el run_id de la ejecución para poder
  correlacionar logs con la tabla etl_auditoria.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.configuracion import CONFIG, resolver_ruta

FORMATO_POR_DEFECTO = "%(asctime)s | %(levelname)s | %(run_id)s | %(name)s | %(message)s"


class FiltroRunId(logging.Filter):
    """Añade el atributo run_id a todos los registros de log."""

    def __init__(self, run_id: str = "-"):
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = self.run_id
        return True


def obtener_ruta_log() -> Path:
    return resolver_ruta(CONFIG["rutas"]["logs"]) / CONFIG["logging"]["archivo"]


def configurar_logging(run_id: str = "-") -> Path:
    """
    Configura el logger raíz. Es idempotente: si se llama varias veces
    (por ejemplo, en tests o en ejecuciones sucesivas) reemplaza los
    handlers creados por este módulo en lugar de duplicarlos.

    Devuelve la ruta del archivo de log.
    """

    config_logs = CONFIG["logging"]

    ruta_log = obtener_ruta_log()
    ruta_log.parent.mkdir(parents=True, exist_ok=True)

    nivel = getattr(logging, str(config_logs.get("nivel", "INFO")).upper(), logging.INFO)

    formatter = logging.Formatter(
        config_logs.get("formato", FORMATO_POR_DEFECTO),
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    filtro = FiltroRunId(run_id)

    raiz = logging.getLogger()
    raiz.setLevel(nivel)

    for handler in list(raiz.handlers):
        if getattr(handler, "_handler_etl", False):
            raiz.removeHandler(handler)
            handler.close()

    consola = logging.StreamHandler(sys.stdout)

    archivo = RotatingFileHandler(
        ruta_log,
        maxBytes=config_logs.get("max_bytes", 5 * 1024 * 1024),
        backupCount=config_logs.get("backup_count", 5),
        encoding=config_logs.get("encoding", "utf-8"),
    )

    for handler in (consola, archivo):
        handler.setFormatter(formatter)
        handler.addFilter(filtro)
        handler._handler_etl = True
        raiz.addHandler(handler)

    return ruta_log
