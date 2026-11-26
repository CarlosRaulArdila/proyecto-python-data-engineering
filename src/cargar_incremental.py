"""
Etapa 4 - Carga incremental (UPSERT) en PostgreSQL.

- Inserta registros nuevos.
- Actualiza solo los registros cuya información cambió
  (IS DISTINCT FROM), por lo que una re-ejecución sin cambios
  realiza 0 operaciones (idempotencia).

Requiere el índice único sobre la clave de negocio creado por
sql/migraciones/V001__crear_hospital_registros.sql.
"""

import logging
import re

import pandas as pd
from sqlalchemy import text

from src.conexion_db import obtener_engine
from src.configuracion import CONFIG, resolver_ruta

logger = logging.getLogger(__name__)

# Obtener configuración desde config.yaml
PROCESSED_DIR = resolver_ruta(CONFIG["rutas"]["processed"])
RUTA_ARCHIVO = PROCESSED_DIR / CONFIG["archivos"]["validados"]

ESQUEMA_DESTINO = CONFIG["base_datos"]["esquema"]
TABLA_DESTINO = CONFIG["base_datos"]["tabla_destino"]
TABLA_CONFIGURADA = f"{ESQUEMA_DESTINO}.{TABLA_DESTINO}"

# Solo se permiten identificadores simples esquema.tabla (evita inyección SQL)
PATRON_TABLA = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$")

COLUMNAS_ENTERAS = ("edad", "duracion_minutos")


def preparar_datos(ruta_archivo):
    """Lee el archivo validado y normaliza los tipos para PostgreSQL."""

    if not ruta_archivo.exists():
        raise FileNotFoundError(f"No se encontró el archivo validado: {ruta_archivo}")

    df = pd.read_csv(
        ruta_archivo,
        dtype={"numero_historia": str},
        encoding="utf-8-sig",
    )

    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date

    # Los CSV con vacíos guardan los enteros como 33.0: se normalizan a int
    for columna in COLUMNAS_ENTERAS:
        if columna in df.columns:
            df[columna] = pd.to_numeric(df[columna]).astype("int64")

    return df


def construir_consulta(tabla, tablas_permitidas=None):
    """Construye el UPSERT para una tabla permitida."""

    tablas_permitidas = tablas_permitidas or {TABLA_CONFIGURADA}

    if tabla not in tablas_permitidas or not PATRON_TABLA.match(tabla):
        raise ValueError(f"Tabla no permitida: {tabla}")

    consulta = text(f"""
        INSERT INTO {tabla} AS destino (
            numero_historia,
            fecha,
            edad,
            especialidad,
            tecnica_anestesica,
            duracion_minutos,
            hospital_origen
        )
        VALUES (
            :numero_historia,
            :fecha,
            :edad,
            :especialidad,
            :tecnica_anestesica,
            :duracion_minutos,
            :hospital_origen
        )
        ON CONFLICT (
            numero_historia,
            fecha,
            hospital_origen
        )
        DO UPDATE SET
            edad = EXCLUDED.edad,
            especialidad = EXCLUDED.especialidad,
            tecnica_anestesica = EXCLUDED.tecnica_anestesica,
            duracion_minutos = EXCLUDED.duracion_minutos,
            fecha_actualizacion = CURRENT_TIMESTAMP
        WHERE
            destino.edad IS DISTINCT FROM EXCLUDED.edad
            OR destino.especialidad IS DISTINCT FROM EXCLUDED.especialidad
            OR destino.tecnica_anestesica IS DISTINCT FROM EXCLUDED.tecnica_anestesica
            OR destino.duracion_minutos IS DISTINCT FROM EXCLUDED.duracion_minutos;
    """)  # noqa: S608 - la tabla se valida contra una lista blanca

    return consulta


def cargar_incremental(df, conexion, tabla=TABLA_CONFIGURADA, tablas_permitidas=None):
    """Ejecuta el UPSERT y devuelve el número de filas insertadas o actualizadas."""

    if df.empty:
        return 0

    consulta = construir_consulta(tabla, tablas_permitidas)
    registros = df.to_dict(orient="records")

    resultado = conexion.execute(consulta, registros)

    return resultado.rowcount


def ejecutar_carga_incremental() -> dict:
    """Ejecuta la etapa y devuelve sus métricas para la auditoría."""

    df = preparar_datos(RUTA_ARCHIVO)

    with obtener_engine().begin() as conexion:
        operaciones = cargar_incremental(df, conexion)

    logger.info(
        "Carga incremental finalizada | Registros procesados: %s | "
        "Operaciones (insertados o actualizados): %s | Tabla: %s",
        len(df),
        operaciones,
        TABLA_CONFIGURADA,
    )

    return {"operaciones_bd": operaciones}


if __name__ == "__main__":
    from src.registro_logs import configurar_logging

    configurar_logging()
    ejecutar_carga_incremental()
