"""
Etapa 2 - Limpieza: separa registros incompletos, duplicados exactos
y conflictos de clave de negocio.
"""

import logging

import pandas as pd

from src.configuracion import CONFIG, resolver_ruta
from src.esquema import obtener_esquema

logger = logging.getLogger(__name__)

# Obtener rutas desde config.yaml
PROCESSED_DIR = resolver_ruta(CONFIG["rutas"]["processed"])
REJECTED_DIR = resolver_ruta(CONFIG["rutas"]["rejected"])

# Obtener nombres de archivos desde config.yaml
ARCHIVOS = CONFIG["archivos"]

INPUT_FILE = PROCESSED_DIR / ARCHIVOS["consolidados"]
OUTPUT_LIMPIOS = PROCESSED_DIR / ARCHIVOS["limpios"]
OUTPUT_INCOMPLETOS = REJECTED_DIR / ARCHIVOS["incompletos"]
OUTPUT_DUPLICADOS = REJECTED_DIR / ARCHIVOS["duplicados"]
OUTPUT_CONFLICTOS = REJECTED_DIR / ARCHIVOS.get(
    "conflictos_clave", "registros_conflicto_clave.csv"
)

# Columnas que identifican un registro de negocio (misma clave del UPSERT)
CLAVE_NEGOCIO = CONFIG["pipeline"]["clave_negocio"]


def detectar_vacios(df):
    """Marca como vacío un valor nulo o un texto compuesto solo por espacios."""

    vacios = df.isna()

    for columna in df.columns:
        serie = df[columna]

        if pd.api.types.is_object_dtype(serie) or pd.api.types.is_string_dtype(serie):
            vacios[columna] = vacios[columna] | serie.astype(str).str.strip().eq("")

    return vacios


def limpiar_datos(df, columnas_obligatorias=None):
    """
    Separa los registros incompletos, detecta duplicados
    exactos y devuelve los registros limpios.

    columnas_obligatorias: columnas que no pueden estar vacías. Si no se
    indica, se consideran todas (comportamiento original).
    """

    # Separar registros incompletos (vacíos o solo espacios)
    columnas = list(columnas_obligatorias) if columnas_obligatorias else list(df.columns)
    mascara_incompletos = detectar_vacios(df[columnas]).any(axis=1)

    df_incompletos = df.loc[mascara_incompletos].copy()
    df_completos = df.loc[~mascara_incompletos].copy()

    # Detectar duplicados exactos
    mascara_duplicados = df_completos.duplicated(keep="first")

    df_duplicados = df_completos.loc[mascara_duplicados].copy()

    # Conservar una sola copia de cada registro
    df_limpio = df_completos.loc[~mascara_duplicados].copy()

    return df_limpio, df_incompletos, df_duplicados


def separar_conflictos_clave(df, clave):
    """
    Detecta registros que comparten la clave de negocio pero tienen
    valores distintos (no son duplicados exactos).

    Se rechazan TODAS las versiones en conflicto: elegir una de forma
    arbitraria cargaría datos que nadie validó. Deben corregirse en
    la fuente.

    Devuelve (df_sin_conflictos, df_conflictos).
    """

    columnas_faltantes = [c for c in clave if c not in df.columns]

    if columnas_faltantes:
        raise ValueError(
            f"Faltan columnas de la clave de negocio: {columnas_faltantes}"
        )

    mascara = df.duplicated(subset=clave, keep=False)

    df_conflictos = df.loc[mascara].copy()
    df_conflictos["motivo_rechazo"] = (
        "Clave de negocio repetida con valores distintos: " + ", ".join(clave)
    )

    return df.loc[~mascara].copy(), df_conflictos


def ejecutar_limpieza() -> dict:
    """Ejecuta la etapa y devuelve sus métricas para la auditoría."""

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"No se encontró el archivo consolidado: {INPUT_FILE}")

    esquema = obtener_esquema(CONFIG)

    df = pd.read_csv(INPUT_FILE, dtype=esquema.dtypes_lectura(), encoding="utf-8-sig")

    df_limpio, df_incompletos, df_duplicados = limpiar_datos(df, esquema.obligatorias)
    df_limpio, df_conflictos = separar_conflictos_clave(df_limpio, CLAVE_NEGOCIO)

    salidas = {
        OUTPUT_INCOMPLETOS: df_incompletos,
        OUTPUT_DUPLICADOS: df_duplicados,
        OUTPUT_CONFLICTOS: df_conflictos,
        OUTPUT_LIMPIOS: df_limpio,
    }

    for ruta, datos in salidas.items():
        datos.to_csv(ruta, index=False, encoding="utf-8-sig")

    rechazados = len(df_incompletos) + len(df_duplicados) + len(df_conflictos)

    logger.info(
        "Limpieza completada | Originales: %s | Incompletos: %s | "
        "Duplicados: %s | Conflictos de clave: %s | Limpios: %s",
        len(df),
        len(df_incompletos),
        len(df_duplicados),
        len(df_conflictos),
        len(df_limpio),
    )

    if len(df_conflictos):
        logger.warning(
            "Se rechazaron %s registros por conflicto de clave de negocio. "
            "Revise %s",
            len(df_conflictos),
            OUTPUT_CONFLICTOS,
        )

    return {
        "registros_limpios": len(df_limpio),
        "registros_rechazados": rechazados,
    }


if __name__ == "__main__":
    from src.registro_logs import configurar_logging

    configurar_logging()
    ejecutar_limpieza()
