
import subprocess
import sys
import logging
import time
from pathlib import Path
from logging.handlers import RotatingFileHandler

# 1. Directorios del proyecto
DIRECTORIO_PROYECTO = Path(__file__).resolve().parent.parent
DIRECTORIO_LOGS = DIRECTORIO_PROYECTO / "logs"

# Crear carpeta de logs si no existe
DIRECTORIO_LOGS.mkdir(parents=True, exist_ok=True)

# 2. Configurar logging
logger = logging.getLogger()

logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    DIRECTORIO_LOGS / "pipeline.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8"
)

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

handler.setFormatter(formatter)

logger.addHandler(handler)

# 3. Scripts que ejecutará el pipeline
TAREAS = [
    "consolidar_datos.py",
    "limpiar_datos.py",
    "validar_reglas.py",
    "cargar_incremental.py"
]

# 4. Ejecutar pipeline
def ejecutar_pipeline():

    inicio = time.perf_counter()

    print("\n===================================")
    print("INICIANDO PIPELINE ETL")
    print("===================================")

    logging.info("INICIO DEL PIPELINE ETL")

    for tarea in TAREAS:

        ruta_script = DIRECTORIO_PROYECTO / "src" / tarea

        print(f"\nEjecutando: {tarea}")
        logging.info(f"Iniciando tarea: {tarea}")

        inicio_tarea = time.perf_counter()

        try:
            resultado = subprocess.run(
                [sys.executable, str(ruta_script)],
                cwd=DIRECTORIO_PROYECTO,
                check=True,
                capture_output=True,
                text=True
            )

            # Mostrar y guardar la salida normal del script
            if resultado.stdout:
                print(resultado.stdout, end="")
                logging.info(
                    f"Salida de {tarea}:\n{resultado.stdout.strip()}"
                )

            # Mostrar y registrar advertencias o mensajes de error
            if resultado.stderr:
                print(resultado.stderr, end="", file=sys.stderr)
                logging.warning(
                    f"Salida de error de {tarea}:\n{resultado.stderr.strip()}"
                )

            duracion = time.perf_counter() - inicio_tarea
            print(f"Correcto: {tarea}")
            logging.info(
                f"Tarea completada: {tarea} | Duración: {duracion:.2f} segundos"
            )

        except subprocess.CalledProcessError as error:
            logging.error(
                f"Error en la tarea: {tarea} | Código: {error.returncode}"
            )

            if error.stdout:
                logging.error(f"Salida del script:\n{error.stdout}")

            if error.stderr:
                logging.error(f"Error detallado del script:\n{error.stderr}")

            print(f"ERROR: Falló la tarea {tarea}")
            sys.exit(1)

        except Exception:
            logging.exception(
                f"Error inesperado durante la tarea: {tarea}"
            )

            print(f"ERROR INESPERADO: {tarea}")
            sys.exit(1)

  
    duracion_total = time.perf_counter() - inicio

    logging.info(
        f"PIPELINE FINALIZADO | Duración total: {duracion_total:.2f} segundos"
    )

    print("\n===================================")
    print("PIPELINE ETL FINALIZADO")
    print(f"Duración: {duracion_total:.2f} segundos")
    print("===================================")


if __name__ == "__main__":
    ejecutar_pipeline()
