"""
Historial de registros rechazados en la base de datos.

La etapa `registrar_rechazos` lee los archivos de rechazados que generan
la limpieza y la validación en la ejecución actual y los inserta en
<base_datos.esquema>.etl_rechazos, con:

- run_id y pipeline_id de la ejecución
- tipo:   incompleto | duplicado | conflicto_clave | regla_negocio
- motivo: por qué se rechazó (columnas vacías, reglas incumplidas...)
- fuente: valor de pipeline.columna_fuente
- registro: el registro original completo, en JSON

Va después de la validación y ANTES de los umbrales de calidad: si un
umbral detiene la carga, los rechazos que lo provocaron quedan guardados
para investigarlos.

Consulta típica:
    SELECT tipo, motivo, count(*) FROM etl_rechazos
    WHERE run_id = '<run_id>' GROUP BY 1, 2 ORDER BY 3 DESC;
"""

import json
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from src.configuracion import CONFIG, resolver_ruta
from src.sql_utils import nombre_tabla

logger = logging.getLogger(__name__)

COLUMNA_MOTIVO_LIMPIEZA = "motivo_rechazo"
COLUMNA_MOTIVO_VALIDACION = "errores_validacion"

TABLA_RECHAZOS = nombre_tabla(
    CONFIG["base_datos"]["esquema"],
    CONFIG["base_datos"].get("tabla_rechazos", "etl_rechazos"),
)

REJECTED_DIR = resolver_ruta(CONFIG["rutas"]["rejected"])

# tipo de rechazo -> (clave en config.archivos, columna con el motivo)
FUENTES_RECHAZO = {
    "incompleto": ("incompletos", COLUMNA_MOTIVO_LIMPIEZA),
    "duplicado": ("duplicados", COLUMNA_MOTIVO_LIMPIEZA),
    "conflicto_clave": ("conflictos_clave", COLUMNA_MOTIVO_LIMPIEZA),
    "regla_negocio": ("fuera_reglas", COLUMNA_MOTIVO_VALIDACION),
}


def _valor_json(valor):
    """Convierte valores de pandas a tipos JSON (NaN -> null)."""

    if valor is None:
        return None

    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass

    return valor


def filas_de_rechazo(
    df: pd.DataFrame,
    tipo: str,
    columna_motivo: str,
    columna_fuente: str,
    run_id: str,
    pipeline_id: str,
) -> list[dict]:
    """Convierte un DataFrame de rechazados en filas para etl_rechazos."""

    filas = []

    for registro in df.to_dict(orient="records"):
        motivo = registro.pop(columna_motivo, None)
        datos = {clave: _valor_json(valor) for clave, valor in registro.items()}

        filas.append(
            {
                "run_id": run_id,
                "pipeline_id": pipeline_id,
                "tipo": tipo,
                "motivo": _valor_json(motivo) or "Sin motivo informado",
                "fuente": datos.get(columna_fuente),
                "registro": json.dumps(datos, ensure_ascii=False, default=str),
            }
        )

    return filas


def leer_rechazados(ruta: Path) -> pd.DataFrame:
    """Lee un archivo de rechazados como texto (vacío si no existe o no tiene filas)."""

    if not ruta.exists() or ruta.stat().st_size == 0:
        return pd.DataFrame()

    try:
        return pd.read_csv(ruta, dtype=str, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def registrar_rechazos(contexto: dict | None = None) -> dict:
    """Etapa del pipeline: guarda los rechazos de esta ejecución en la base."""

    from src.conexion_db import obtener_engine

    contexto = contexto or {}
    run_id = contexto.get("run_id")
    pipeline_id = contexto.get("pipeline_id") or CONFIG["pipeline"]["id"]
    columna_fuente = CONFIG["pipeline"]["columna_fuente"]

    if not run_id:
        raise RuntimeError("registrar_rechazos requiere el run_id de la ejecución.")

    filas = []
    resumen = {}

    for tipo, (clave_archivo, columna_motivo) in FUENTES_RECHAZO.items():
        nombre = CONFIG["archivos"].get(clave_archivo)

        if not nombre:
            continue

        df = leer_rechazados(REJECTED_DIR / nombre)

        if df.empty:
            continue

        nuevas = filas_de_rechazo(df, tipo, columna_motivo, columna_fuente, run_id, pipeline_id)
        filas.extend(nuevas)
        resumen[tipo] = len(nuevas)

    if not filas:
        logger.info("No hay registros rechazados que guardar.")
        return {"rechazos_registrados": 0}

    with obtener_engine().begin() as conexion:
        conexion.execute(
            text(
                f"INSERT INTO {TABLA_RECHAZOS} "
                "(run_id, pipeline_id, tipo, motivo, fuente, registro) "
                "VALUES (:run_id, :pipeline_id, :tipo, :motivo, :fuente, "
                "CAST(:registro AS JSONB))"
            ),
            filas,
        )

    logger.info("Rechazos guardados en %s: %s", TABLA_RECHAZOS, resumen)

    return {"rechazos_registrados": len(filas)}
