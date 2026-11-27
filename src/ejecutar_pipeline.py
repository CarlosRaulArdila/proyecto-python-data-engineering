"""
Orquestador del pipeline ETL.

Ejecuta, en el orden de config.yaml (pipeline.tareas), las funciones
de cada etapa dentro del mismo proceso. Cada etapa devuelve un
diccionario de métricas, que el orquestador acumula y registra en
public.etl_auditoria.

Antes se lanzaba un subproceso por etapa y las métricas se obtenían
leyendo su salida estándar con expresiones regulares y comparando
nombres de archivo. Ahora:
- Añadir una etapa nueva es declarar módulo y función en config.yaml.
- Las métricas no dependen del texto que imprima cada etapa.
- El aislamiento del proceso lo proporciona el contenedor Docker.

Uso:
    python -m src.ejecutar_pipeline

Código de salida: 0 si la ejecución es EXITOSA, 1 en cualquier otro caso.
"""

import importlib
import inspect
import logging
import os
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from src import alertas, auditoria
from src.conexion_db import cerrar_engine
from src.configuracion import CONFIG
from src.registro_logs import configurar_logging

logger = logging.getLogger(__name__)

# Métricas que se registran en etl_auditoria
METRICAS = (
    "registros_extraidos",
    "registros_limpios",
    "registros_rechazados",
    "operaciones_bd",
)

# Métricas que se suman entre etapas (el resto conserva el último valor)
METRICAS_ACUMULABLES = {"registros_rechazados", "operaciones_bd"}


@dataclass(frozen=True)
class Tarea:
    nombre: str
    funcion: Callable[..., dict | None]

    def ejecutar(self, contexto: dict) -> dict | None:
        """
        Llama a la función de la etapa. Si acepta un parámetro, recibe el
        contexto de la ejecución (run_id, pipeline_id, errores previos...).
        """

        try:
            acepta_contexto = bool(inspect.signature(self.funcion).parameters)
        except (TypeError, ValueError):
            acepta_contexto = False

        return self.funcion(contexto) if acepta_contexto else self.funcion()


def resolver_tarea(definicion: dict) -> Tarea:
    """
    Convierte una entrada de pipeline.tareas en una tarea ejecutable.

    Formato esperado en config.yaml:
        - nombre: "consolidar"
          modulo: "src.consolidar_datos"
          funcion: "ejecutar_consolidacion"
    """

    if not isinstance(definicion, dict):
        raise ValueError(
            f"Definición de tarea no válida: {definicion!r}. "
            "Cada tarea debe declarar 'nombre', 'modulo' y 'funcion' "
            "(ver config/config.yaml)."
        )

    faltantes = [c for c in ("nombre", "modulo", "funcion") if c not in definicion]

    if faltantes:
        raise ValueError(f"A la tarea {definicion!r} le faltan las claves: {faltantes}")

    modulo = importlib.import_module(definicion["modulo"])
    funcion = getattr(modulo, definicion["funcion"], None)

    if not callable(funcion):
        raise ValueError(
            f"La función {definicion['funcion']} no existe en {definicion['modulo']}"
        )

    return Tarea(nombre=definicion["nombre"], funcion=funcion)


def acumular_metricas(totales: dict, nuevas: dict | None) -> dict:
    """Incorpora las métricas devueltas por una etapa."""

    for clave, valor in (nuevas or {}).items():
        if clave not in METRICAS:
            continue

        if clave in METRICAS_ACUMULABLES:
            totales[clave] = totales.get(clave, 0) + int(valor)
        else:
            totales[clave] = int(valor)

    return totales


def obtener_contexto() -> dict:
    """Identificación de la ejecución (variables de entorno > config.yaml)."""

    proyecto = CONFIG["proyecto"]
    pipeline = CONFIG["pipeline"]

    return {
        "proyecto_id": proyecto["nombre"],
        "pipeline_id": os.getenv("ETL_PIPELINE_ID", pipeline.get("id", "pipeline_principal")),
        "orquestador": os.getenv("ETL_ORCHESTRATOR", "manual"),
        "version_pipeline": os.getenv("ETL_PIPELINE_VERSION", proyecto.get("version", "0.0.0")),
        "ambiente": os.getenv("ETL_ENVIRONMENT", proyecto.get("entorno", "desarrollo")),
    }


def ejecutar_pipeline(tareas: list[Tarea] | None = None) -> int:
    """Ejecuta el pipeline completo con auditoría. Devuelve el código de salida."""

    inicio = time.perf_counter()
    run_id = str(uuid.uuid4())
    ruta_log = configurar_logging(run_id)
    contexto = obtener_contexto()

    detener_si_falla = CONFIG["pipeline"].get("detener_si_falla", True)

    metricas = dict.fromkeys(METRICAS, 0)
    errores: list[str] = []
    advertencias: list[str] = []
    detalle: dict = {}  # todas las métricas devueltas por las etapas (último valor)
    id_ejecucion = None
    estado = auditoria.ESTADO_FALLIDO

    logger.info("INICIO DEL PIPELINE ETL | %s", contexto)

    try:
        # Si no se puede auditar, no se ejecuta: la trazabilidad es obligatoria
        id_ejecucion = auditoria.registrar_inicio(
            run_id=run_id,
            archivo_log=str(ruta_log),
            **contexto,
        )
        logger.info("Auditoría iniciada | ID: %s", id_ejecucion)

        # Información de la ejecución disponible para las etapas que la usen
        contexto_ejecucion = {
            "run_id": run_id,
            "id_ejecucion": id_ejecucion,
            "pipeline_id": contexto["pipeline_id"],
            "errores": errores,
            "advertencias": advertencias,
            "metricas": metricas,
            "detalle": detalle,
        }

        if tareas is None:
            tareas = [resolver_tarea(t) for t in CONFIG["pipeline"]["tareas"]]

        for tarea in tareas:
            inicio_tarea = time.perf_counter()
            logger.info("Iniciando tarea: %s", tarea.nombre)

            try:
                resultado = tarea.ejecutar(contexto_ejecucion)

            except Exception as error:
                logger.exception("La tarea %s ha fallado", tarea.nombre)
                errores.append(f"{tarea.nombre}: {error}")

                if detener_si_falla:
                    raise

                continue

            acumular_metricas(metricas, resultado)
            detalle.update(resultado or {})

            logger.info(
                "Tarea completada: %s | Duración: %.2f s | Métricas: %s",
                tarea.nombre,
                time.perf_counter() - inicio_tarea,
                resultado or {},
            )

        estado = auditoria.ESTADO_PARCIAL if errores else auditoria.ESTADO_EXITOSO

    except Exception as error:
        estado = auditoria.ESTADO_FALLIDO

        if id_ejecucion is None:
            logger.exception(
                "No fue posible registrar el inicio en la auditoría. "
                "El pipeline no se ejecutó."
            )
        elif errores:
            # El detalle ya se registró al fallar la tarea
            logger.error("El pipeline ETL ha fallado.")
        else:
            logger.exception("El pipeline ETL ha fallado.")

        if not errores:
            errores.append(str(error))

    duracion_total = time.perf_counter() - inicio
    mensaje_error = " | ".join(errores) or None
    texto_advertencias = " | ".join(advertencias) or None

    if id_ejecucion is not None:
        try:
            auditoria.registrar_fin(
                id_ejecucion=id_ejecucion,
                estado=estado,
                duracion_segundos=duracion_total,
                mensaje_error=mensaje_error,
                advertencias=texto_advertencias,
                **metricas,
            )
            logger.info("Auditoría cerrada | ID: %s | Estado: %s", id_ejecucion, estado)

        except Exception:
            logger.exception("No fue posible cerrar el registro de auditoría.")
            estado = auditoria.ESTADO_FALLIDO

    logger.info(
        "PIPELINE FINALIZADO | Estado: %s | Duración: %.2f s | Métricas: %s",
        estado,
        duracion_total,
        metricas,
    )

    if advertencias:
        logger.warning("Advertencias de la ejecución: %s", texto_advertencias)

    # Alertas: nunca alteran el estado ni el código de salida
    alertas.notificar(
        {
            **contexto,
            "estado": estado,
            "run_id": run_id,
            "id_ejecucion": id_ejecucion,
            "duracion_segundos": duracion_total,
            "metricas": metricas,
            "mensaje_error": mensaje_error,
            "advertencias": texto_advertencias,
            "archivo_log": str(ruta_log),
        }
    )

    cerrar_engine()

    return 0 if estado == auditoria.ESTADO_EXITOSO else 1


if __name__ == "__main__":
    sys.exit(ejecutar_pipeline())
