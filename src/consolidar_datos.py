"""
Etapa 1 - Consolidación: une los archivos de las fuentes configuradas
en config.yaml en un único CSV.

- Cada fuente se declara con 'archivo' (exacto) o 'patron' (lotes).
- En modo de ingesta 'incremental' se omiten los archivos ya cargados
  (ver src/ingesta.py).
- Escribe un manifiesto con los archivos usados, que la etapa final
  registra en etl_archivos_procesados si toda la carga termina bien.
"""

import logging
from pathlib import Path

import pandas as pd

from src.configuracion import CONFIG, resolver_ruta
from src.esquema import Esquema, obtener_esquema
from src.ingesta import (
    ArchivoFuente,
    archivos_no_configurados,
    descubrir_archivos,
    entrada_manifiesto,
    escribir_manifiesto,
    filtrar_nuevos,
    hashes_procesados,
    modo_ingesta,
)

logger = logging.getLogger(__name__)

# Obtener las rutas desde la configuración
RAW_DIR = resolver_ruta(CONFIG["rutas"]["raw"])
PROCESSED_DIR = resolver_ruta(CONFIG["rutas"]["processed"])

# Columna derivada donde se guarda el nombre de la fuente de cada registro
COLUMNA_FUENTE = CONFIG["pipeline"]["columna_fuente"]


def leer_fuente(
    ruta: Path,
    fuente: str,
    esquema: Esquema | None = None,
    columna_fuente: str | None = None,
) -> pd.DataFrame:
    """Lee un archivo de origen y añade la columna con el nombre de la fuente."""

    # Sin esquema se lee todo como texto: nunca se pierden ceros iniciales
    dtypes = esquema.dtypes_lectura() if esquema else str

    df = pd.read_csv(ruta, dtype=dtypes, encoding="utf-8-sig")

    if esquema:
        df = esquema.ajustar_columnas_fuente(df, ruta.name).copy()

    df[columna_fuente or COLUMNA_FUENTE] = fuente

    return df


def consolidar_datos(
    archivos: dict[str, str],
    raw_dir: Path,
    esquema: Esquema | None = None,
) -> pd.DataFrame:
    """
    Lee los archivos CSV indicados y los consolida en un único DataFrame,
    añadiendo la columna de la fuente (pipeline.columna_fuente).

    archivos: {nombre_archivo: nombre_fuente}
    esquema:  si se indica, se usan sus tipos de lectura y se exige que
              cada fuente tenga sus columnas (las sobrantes se descartan).
    """

    lista_fuentes = []

    for archivo, fuente in archivos.items():
        ruta = raw_dir / archivo

        if not ruta.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {ruta}")

        df = leer_fuente(ruta, fuente, esquema)
        lista_fuentes.append(df)

        logger.info("%s: %s registros cargados", fuente, len(df))

    if not lista_fuentes:
        raise ValueError("No se encontraron archivos para consolidar.")

    return pd.concat(lista_fuentes, ignore_index=True)


def detectar_archivos_no_configurados(raw_dir: Path, configurados) -> list[str]:
    """CSV presentes en raw_dir que no están en la lista de archivos configurados."""

    return archivos_no_configurados([{"archivo": a} for a in configurados], raw_dir)


def seleccionar_archivos(
    archivos: list[ArchivoFuente], modo: str, pipeline_id: str
) -> list[ArchivoFuente]:
    """En modo incremental, descarta los archivos ya registrados."""

    if modo != "incremental" or not archivos:
        return archivos

    from src.conexion_db import obtener_engine

    with obtener_engine().connect() as conexion:
        ya_procesados = hashes_procesados(
            conexion, pipeline_id, [a.hash_sha256 for a in archivos]
        )

    nuevos, omitidos = filtrar_nuevos(archivos, ya_procesados)

    for archivo in omitidos:
        logger.info("Omitido (ya procesado): %s [%s]", archivo.nombre, archivo.fuente)

    logger.info(
        "Ingesta incremental | Archivos encontrados: %s | Nuevos: %s | Omitidos: %s",
        len(archivos),
        len(nuevos),
        len(omitidos),
    )

    return nuevos


def ejecutar_consolidacion(contexto: dict | None = None) -> dict:
    """Ejecuta la etapa y devuelve sus métricas para la auditoría."""

    contexto = contexto or {}
    fuentes = CONFIG["fuentes"]
    esquema = obtener_esquema(CONFIG)
    modo = modo_ingesta(CONFIG)
    pipeline_id = contexto.get("pipeline_id") or CONFIG["pipeline"]["id"]

    no_configurados = archivos_no_configurados(fuentes, RAW_DIR)

    if no_configurados:
        logger.warning(
            "Archivos en %s que NO se procesan porque no están en "
            "config.yaml (fuentes): %s",
            RAW_DIR,
            ", ".join(no_configurados),
        )

    archivos = seleccionar_archivos(descubrir_archivos(fuentes, RAW_DIR), modo, pipeline_id)

    partes, manifiesto = [], []

    for archivo in archivos:
        df = leer_fuente(archivo.ruta, archivo.fuente, esquema)
        partes.append(df)
        manifiesto.append(entrada_manifiesto(archivo, len(df)))

        logger.info("%s: %s registros cargados (%s)", archivo.fuente, len(df), archivo.nombre)

    if partes:
        df_consolidado = pd.concat(partes, ignore_index=True)
    else:
        logger.info("No hay archivos nuevos para procesar.")
        df_consolidado = pd.DataFrame(columns=esquema.nombres)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ruta_salida = PROCESSED_DIR / CONFIG["archivos"]["consolidados"]

    df_consolidado.to_csv(ruta_salida, index=False, encoding="utf-8-sig")
    escribir_manifiesto(manifiesto, contexto.get("run_id"))

    logger.info(
        "Consolidación completada | Modo: %s | Archivos: %s | Registros: %s | "
        "Columnas: %s | Archivo: %s",
        modo,
        len(archivos),
        len(df_consolidado),
        len(df_consolidado.columns),
        ruta_salida,
    )

    return {"registros_extraidos": len(df_consolidado), "archivos_procesados": len(archivos)}


if __name__ == "__main__":
    from src.registro_logs import configurar_logging

    configurar_logging()
    ejecutar_consolidacion()
