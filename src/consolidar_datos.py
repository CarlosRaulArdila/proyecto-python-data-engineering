"""
Etapa 1 - Consolidación: une los archivos de las fuentes configuradas
en config.yaml en un único CSV.
"""

import logging
from pathlib import Path

import pandas as pd

from src.configuracion import CONFIG, resolver_ruta
from src.esquema import Esquema, obtener_esquema

logger = logging.getLogger(__name__)

# Obtener las rutas desde la configuración
RAW_DIR = resolver_ruta(CONFIG["rutas"]["raw"])
PROCESSED_DIR = resolver_ruta(CONFIG["rutas"]["processed"])


def consolidar_datos(
    archivos: dict[str, str],
    raw_dir: Path,
    esquema: Esquema | None = None,
) -> pd.DataFrame:
    """
    Lee los archivos CSV de las fuentes y los consolida en un único
    DataFrame, añadiendo la columna hospital_origen.

    archivos: {nombre_archivo: nombre_fuente}
    esquema:  si se indica, se usan sus tipos de lectura y se exige que
              cada fuente tenga sus columnas (las sobrantes se descartan).
    """

    # Sin esquema se lee todo como texto: nunca se pierden ceros iniciales
    dtypes = esquema.dtypes_lectura() if esquema else str

    lista_fuentes = []

    for archivo, fuente in archivos.items():
        ruta = raw_dir / archivo

        if not ruta.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {ruta}")

        df = pd.read_csv(ruta, dtype=dtypes, encoding="utf-8-sig")

        if esquema:
            df = esquema.ajustar_columnas_fuente(df, archivo).copy()

        df["hospital_origen"] = fuente
        lista_fuentes.append(df)

        logger.info("%s: %s registros cargados", fuente, len(df))

    if not lista_fuentes:
        raise ValueError("No se encontraron archivos para consolidar.")

    return pd.concat(lista_fuentes, ignore_index=True)


def detectar_archivos_no_configurados(raw_dir: Path, configurados) -> list[str]:
    """
    Devuelve los CSV presentes en raw_dir que no están declarados en
    config.yaml. Antes se ignoraban sin aviso.
    """

    configurados = set(configurados)

    return sorted(
        ruta.name
        for ruta in raw_dir.glob("*.csv")
        if ruta.name not in configurados
    )


def ejecutar_consolidacion() -> dict:
    """Ejecuta la etapa y devuelve sus métricas para la auditoría."""

    archivos = {fuente["archivo"]: fuente["nombre"] for fuente in CONFIG["fuentes"]}

    no_configurados = detectar_archivos_no_configurados(RAW_DIR, archivos)

    if no_configurados:
        logger.warning(
            "Archivos en %s que NO se procesan porque no están en "
            "config.yaml (fuentes): %s",
            RAW_DIR,
            ", ".join(no_configurados),
        )

    df_consolidado = consolidar_datos(archivos, RAW_DIR, obtener_esquema(CONFIG))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ruta_salida = PROCESSED_DIR / CONFIG["archivos"]["consolidados"]

    df_consolidado.to_csv(ruta_salida, index=False, encoding="utf-8-sig")

    logger.info(
        "Consolidación completada | Registros: %s | Columnas: %s | Archivo: %s",
        len(df_consolidado),
        len(df_consolidado.columns),
        ruta_salida,
    )

    return {"registros_extraidos": len(df_consolidado)}


if __name__ == "__main__":
    from src.registro_logs import configurar_logging

    configurar_logging()
    ejecutar_consolidacion()
