"""
Etapa 3 - Validación: aplica las reglas automáticas del esquema y las
reglas de negocio declaradas en config.yaml (sección `reglas`), y separa
los registros que no las cumplen indicando el motivo.

El motor de reglas está en src/reglas.py.
"""

import logging

import pandas as pd

from src.configuracion import CONFIG, resolver_ruta
from src.esquema import obtener_esquema
from src.reglas import construir_reglas, validar_dataframe

logger = logging.getLogger(__name__)

# Obtener rutas desde config.yaml
PROCESSED_DIR = resolver_ruta(CONFIG["rutas"]["processed"])
REJECTED_DIR = resolver_ruta(CONFIG["rutas"]["rejected"])

# Obtener nombres de archivos desde config.yaml
ARCHIVO_ENTRADA = PROCESSED_DIR / CONFIG["archivos"]["limpios"]
ARCHIVO_VALIDOS = PROCESSED_DIR / CONFIG["archivos"]["validados"]
ARCHIVO_RECHAZADOS = REJECTED_DIR / CONFIG["archivos"]["fuera_reglas"]


def validar_datos(df, esquema=None, reglas=None):
    """
    Aplica las reglas del esquema y las reglas de negocio de config.yaml.
    Devuelve (df_validos, df_rechazados); los rechazados incluyen la
    columna errores_validacion con los motivos.
    """

    esquema = esquema or obtener_esquema(CONFIG)

    if reglas is None:
        reglas = construir_reglas(CONFIG.get("reglas"), esquema)

    return validar_dataframe(df, esquema, reglas)


def ejecutar_validacion() -> dict:
    """Ejecuta la etapa y devuelve sus métricas para la auditoría."""

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)

    if not ARCHIVO_ENTRADA.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de datos limpios: {ARCHIVO_ENTRADA}"
        )

    df = pd.read_csv(
        ARCHIVO_ENTRADA,
        dtype=obtener_esquema(CONFIG).dtypes_lectura(),
        encoding="utf-8-sig",
    )

    df_validos, df_rechazados = validar_datos(df)

    df_validos.to_csv(ARCHIVO_VALIDOS, index=False, encoding="utf-8-sig")
    df_rechazados.to_csv(ARCHIVO_RECHAZADOS, index=False, encoding="utf-8-sig")

    logger.info(
        "Validación completada | Originales: %s | Válidos: %s | Rechazados: %s",
        len(df),
        len(df_validos),
        len(df_rechazados),
    )

    return {
        "registros_validos": len(df_validos),
        "registros_rechazados": len(df_rechazados),
    }


if __name__ == "__main__":
    from src.registro_logs import configurar_logging

    configurar_logging()
    ejecutar_validacion()
