
import subprocess
import sys
import logging
import time
import csv
import re

from pathlib import Path
from logging.handlers import RotatingFileHandler

try:
    from src.configuracion import BASE_DIR, CONFIG
    from src.auditoria import registrar_inicio, registrar_fin
except ModuleNotFoundError:
    from configuracion import BASE_DIR, CONFIG
    from auditoria import registrar_inicio, registrar_fin


# ============================================================
# 1. CONFIGURACIÓN GENERAL DEL PROYECTO
# ============================================================

DIRECTORIO_PROYECTO = BASE_DIR

DIRECTORIO_LOGS = (
    BASE_DIR / CONFIG["rutas"]["logs"]
)

DIRECTORIO_PROCESADOS = (
    BASE_DIR / CONFIG["rutas"]["processed"]
)

DIRECTORIO_RECHAZADOS = (
    BASE_DIR / CONFIG["rutas"]["rejected"]
)

DIRECTORIO_LOGS.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# 2. CONFIGURACIÓN DEL SISTEMA DE LOGS
# ============================================================

CONFIG_LOGS = CONFIG["logging"]

ruta_log = (
    DIRECTORIO_LOGS / CONFIG_LOGS["archivo"]
)

nivel_log = getattr(
    logging,
    CONFIG_LOGS["nivel"].upper(),
    logging.INFO
)

logger = logging.getLogger()
logger.setLevel(nivel_log)

handler = RotatingFileHandler(
    ruta_log,
    maxBytes=CONFIG_LOGS["max_bytes"],
    backupCount=CONFIG_LOGS["backup_count"],
    encoding=CONFIG_LOGS["encoding"]
)

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

handler.setFormatter(formatter)

if not any(
    isinstance(h, RotatingFileHandler)
    and h.baseFilename == handler.baseFilename
    for h in logger.handlers
):
    logger.addHandler(handler)
else:
    handler.close()


# ============================================================
# 3. TAREAS DEL PIPELINE
# ============================================================

TAREAS = CONFIG["pipeline"]["tareas"]


# ============================================================
# 4. NOMBRES DE ARCHIVOS DESDE CONFIG.YAML
# ============================================================

ARCHIVOS = CONFIG["archivos"]


# ============================================================
# 5. CONTAR REGISTROS DE UN ARCHIVO CSV
# ============================================================

def contar_registros(ruta_archivo):

    with open(
        ruta_archivo,
        mode="r",
        encoding="utf-8-sig",
        newline=""
    ) as archivo:

        lector = csv.DictReader(archivo)

        return sum(1 for fila in lector)


# ============================================================
# 6. EXTRAER OPERACIONES DE LA SALIDA DEL SCRIPT
# ============================================================

def obtener_operaciones_bd(salida):

    patron = (
        r"Operaciones realizadas "
        r"\(insertados o actualizados\):\s*(\d+)"
    )

    coincidencia = re.search(patron, salida)

    if not coincidencia:
        raise ValueError(
            "No se pudo identificar el número de operaciones "
            "realizadas en PostgreSQL."
        )

    return int(coincidencia.group(1))


# ============================================================
# 7. EJECUCIÓN DEL PIPELINE
# ============================================================

def ejecutar_pipeline():

    inicio = time.perf_counter()

    print("\n===================================")
    print("INICIANDO PIPELINE ETL")
    print("===================================")

    logging.info("INICIO DEL PIPELINE ETL")

    # --------------------------------------------------------
    # 7.1. REGISTRAR INICIO DE AUDITORÍA
    # --------------------------------------------------------

    id_ejecucion = registrar_inicio()

    logging.info(
        f"Auditoría iniciada | ID de ejecución: {id_ejecucion}"
    )

    # --------------------------------------------------------
    # 7.2. INICIALIZAR MÉTRICAS
    # --------------------------------------------------------

    registros_extraidos = 0
    registros_limpios = 0
    registros_rechazados = 0
    operaciones_bd = 0

    estado = "EXITOSO"
    mensaje_error = None

    # --------------------------------------------------------
    # 7.3. EJECUTAR LAS TAREAS
    # --------------------------------------------------------

    try:

        for tarea in TAREAS:

            nombre_modulo = Path(tarea).stem

            print(f"\nEjecutando: {tarea}")

            logging.info(f"Iniciando tarea: {tarea}")

            inicio_tarea = time.perf_counter()

            resultado = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    f"src.{nombre_modulo}"
                ],
                cwd=DIRECTORIO_PROYECTO,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            # ------------------------------------------------
            # 7.4. REGISTRAR SALIDA DEL SCRIPT
            # ------------------------------------------------

            if resultado.stdout:

                print(resultado.stdout, end="")

                logging.info(
                    f"Salida de {tarea}:\n"
                    f"{resultado.stdout.strip()}"
                )

            if resultado.stderr:

                print(
                    resultado.stderr,
                    end="",
                    file=sys.stderr
                )

                logging.warning(
                    f"Salida de error de {tarea}:\n"
                    f"{resultado.stderr.strip()}"
                )

            # ------------------------------------------------
            # 7.5. CONTABILIZAR REGISTROS EXTRAÍDOS
            # ------------------------------------------------

            if tarea == "consolidar_datos.py":

                ruta_consolidados = (
                    DIRECTORIO_PROCESADOS
                    / ARCHIVOS["consolidados"]
                )

                registros_extraidos = contar_registros(
                    ruta_consolidados
                )

                logging.info(
                    f"Registros extraídos: {registros_extraidos}"
                )

            # ------------------------------------------------
            # 7.6. CONTABILIZAR REGISTROS LIMPIOS Y RECHAZADOS
            # ------------------------------------------------

            if tarea == "limpiar_datos.py":

                ruta_limpios = (
                    DIRECTORIO_PROCESADOS
                    / ARCHIVOS["limpios"]
                )

                registros_limpios = contar_registros(
                    ruta_limpios
                )

                ruta_incompletos = (
                    DIRECTORIO_RECHAZADOS
                    / ARCHIVOS["incompletos"]
                )

                ruta_duplicados = (
                    DIRECTORIO_RECHAZADOS
                    / ARCHIVOS["duplicados"]
                )

                registros_rechazados = (
                    contar_registros(ruta_incompletos)
                    + contar_registros(ruta_duplicados)
                )

                logging.info(
                    f"Registros limpios: {registros_limpios}"
                )

                logging.info(
                    "Registros rechazados durante limpieza: "
                    f"{registros_rechazados}"
                )

            # ------------------------------------------------
            # 7.7. SUMAR RECHAZADOS POR REGLAS DE VALIDACIÓN
            # ------------------------------------------------

            if tarea == "validar_reglas.py":

                ruta_fuera_reglas = (
                    DIRECTORIO_RECHAZADOS
                    / ARCHIVOS["fuera_reglas"]
                )

                rechazados_validacion = contar_registros(
                    ruta_fuera_reglas
                )

                registros_rechazados += rechazados_validacion

                logging.info(
                    "Registros rechazados por reglas: "
                    f"{rechazados_validacion}"
                )

                logging.info(
                    f"Total de registros rechazados: "
                    f"{registros_rechazados}"
                )

            # ------------------------------------------------
            # 7.8. CONTABILIZAR OPERACIONES EN POSTGRESQL
            # ------------------------------------------------

            if tarea == "cargar_incremental.py":

                operaciones_bd = obtener_operaciones_bd(
                    resultado.stdout
                )

                logging.info(
                    f"Operaciones realizadas en PostgreSQL: "
                    f"{operaciones_bd}"
                )

            # ------------------------------------------------
            # 7.9. REGISTRAR DURACIÓN DE CADA TAREA
            # ------------------------------------------------

            duracion_tarea = (
                time.perf_counter() - inicio_tarea
            )

            print(f"Correcto: {tarea}")

            logging.info(
                f"Tarea completada: {tarea} | "
                f"Duración: {duracion_tarea:.2f} segundos"
            )

        # ----------------------------------------------------
        # 7.10. FINALIZACIÓN EXITOSA
        # ----------------------------------------------------

        duracion_total = time.perf_counter() - inicio

        registrar_fin(
            id_ejecucion=id_ejecucion,
            estado="EXITOSO",
            registros_extraidos=registros_extraidos,
            registros_limpios=registros_limpios,
            registros_rechazados=registros_rechazados,
            operaciones_bd=operaciones_bd,
            duracion_segundos=duracion_total,
            mensaje_error=None
        )

        logging.info(
            f"Auditoría finalizada correctamente | "
            f"ID: {id_ejecucion}"
        )

        logging.info(
            f"PIPELINE FINALIZADO | "
            f"Duración total: {duracion_total:.2f} segundos"
        )

        print("\n===================================")
        print("PIPELINE ETL FINALIZADO")
        print(f"Registros extraídos: {registros_extraidos}")
        print(f"Registros limpios: {registros_limpios}")
        print(f"Registros rechazados: {registros_rechazados}")
        print(f"Operaciones en PostgreSQL: {operaciones_bd}")
        print(f"Duración: {duracion_total:.2f} segundos")
        print("Estado: EXITOSO")
        print("===================================")

        return 0

    # --------------------------------------------------------
    # 7.11. GESTIONAR ERRORES DEL PIPELINE
    # --------------------------------------------------------

    except Exception as error:

        estado = "FALLIDO"
        mensaje_error = str(error)

        if isinstance(error, subprocess.CalledProcessError):

            if error.stdout:
                logging.error(
                    f"Salida del script:\n{error.stdout}"
                )

            if error.stderr:
                logging.error(
                    f"Error detallado del script:\n{error.stderr}"
                )

        logging.exception(
            "El pipeline ETL ha fallado."
        )

        duracion_total = time.perf_counter() - inicio

        # ----------------------------------------------------
        # 7.12. REGISTRAR EL FALLO EN LA AUDITORÍA
        # ----------------------------------------------------

        try:

            registrar_fin(
                id_ejecucion=id_ejecucion,
                estado=estado,
                registros_extraidos=registros_extraidos,
                registros_limpios=registros_limpios,
                registros_rechazados=registros_rechazados,
                operaciones_bd=operaciones_bd,
                duracion_segundos=duracion_total,
                mensaje_error=mensaje_error
            )

            logging.info(
                f"Auditoría cerrada con estado FALLIDO | "
                f"ID: {id_ejecucion}"
            )

        except Exception:

            logging.exception(
                "No fue posible cerrar el registro de auditoría."
            )

        print("\n===================================")
        print("PIPELINE ETL FALLIDO")
        print(f"Error: {mensaje_error}")
        print(f"Duración: {duracion_total:.2f} segundos")
        print("Estado: FALLIDO")
        print("===================================")

        return 1


# ============================================================
# 8. PUNTO DE ENTRADA
# ============================================================

if __name__ == "__main__":

    sys.exit(ejecutar_pipeline())
