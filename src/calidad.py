"""
Umbrales de calidad de datos.

Se declaran en la sección `calidad` de config.yaml y se evalúan en la
etapa `evaluar_calidad`, que va entre la validación y la carga:

    calidad:
      max_porcentaje_rechazo: 30     # % de rechazados sobre los extraídos
      min_registros_extraidos: 10    # mínimo esperado por ejecución
      accion: "fallar"               # fallar | advertir

- fallar:   la ejecución se detiene ANTES de cargar (estado FALLIDO). En
            modo incremental los archivos se reintentan en la siguiente
            ejecución, una vez corregida la fuente.
- advertir: se carga normalmente y el incumplimiento queda en la columna
            `advertencias` de la auditoría (y en el log).

Si en una ejecución no hubo archivos nuevos (ingesta incremental), no se
evalúan los umbrales: no recibir datos nuevos no es un error de calidad.
"""

import logging

logger = logging.getLogger(__name__)

ACCIONES = {"fallar", "advertir"}
CLAVES = {"max_porcentaje_rechazo", "min_registros_extraidos", "accion"}


class UmbralCalidadExcedido(RuntimeError):
    """La ejecución no cumple los umbrales de calidad configurados."""


def validar_config_calidad(calidad: dict | None) -> dict:
    """Valida la sección `calidad` y devuelve la configuración normalizada."""

    if not calidad:
        return {}

    if not isinstance(calidad, dict):
        raise ValueError("La sección 'calidad' debe ser un diccionario.")

    desconocidas = set(calidad) - CLAVES

    if desconocidas:
        raise ValueError(
            f"Claves desconocidas en 'calidad': {sorted(desconocidas)}. "
            f"Permitidas: {sorted(CLAVES)}"
        )

    accion = calidad.get("accion", "fallar")

    if accion not in ACCIONES:
        raise ValueError(f"calidad.accion inválida: {accion!r}. Use: {sorted(ACCIONES)}")

    maximo = calidad.get("max_porcentaje_rechazo")

    if maximo is not None and not (isinstance(maximo, int | float) and 0 <= maximo <= 100):
        raise ValueError("calidad.max_porcentaje_rechazo debe ser un número entre 0 y 100.")

    minimo = calidad.get("min_registros_extraidos")

    if minimo is not None and not (isinstance(minimo, int) and minimo >= 0):
        raise ValueError("calidad.min_registros_extraidos debe ser un entero mayor o igual a 0.")

    return {**calidad, "accion": accion}


def evaluar_umbrales(metricas: dict, calidad: dict) -> list[str]:
    """Devuelve la lista de umbrales incumplidos (vacía si todo está bien)."""

    extraidos = metricas.get("registros_extraidos", 0)
    rechazados = metricas.get("registros_rechazados", 0)
    incumplimientos = []

    minimo = calidad.get("min_registros_extraidos")

    if minimo is not None and extraidos < minimo:
        incumplimientos.append(
            f"Se extrajeron {extraidos} registros; el mínimo esperado es {minimo}"
        )

    maximo = calidad.get("max_porcentaje_rechazo")

    if maximo is not None and extraidos > 0:
        porcentaje = rechazados / extraidos * 100

        if porcentaje > maximo:
            incumplimientos.append(
                f"Se rechazó el {porcentaje:.1f} % de los registros "
                f"({rechazados} de {extraidos}); el máximo permitido es {maximo} %"
            )

    return incumplimientos


def evaluar_calidad(contexto: dict | None = None) -> dict:
    """Etapa del pipeline: aplica los umbrales a las métricas acumuladas."""

    from src.configuracion import CONFIG

    contexto = contexto or {}
    calidad = validar_config_calidad(CONFIG.get("calidad"))

    if not calidad:
        logger.info("No hay umbrales de calidad configurados.")
        return {}

    detalle = contexto.get("detalle", {})

    if detalle.get("archivos_procesados") == 0:
        logger.info("Sin archivos nuevos en esta ejecución: no se evalúan los umbrales.")
        return {}

    metricas = contexto.get("metricas", {})
    incumplimientos = evaluar_umbrales(metricas, calidad)

    if not incumplimientos:
        logger.info("Umbrales de calidad cumplidos | Métricas: %s", metricas)
        return {}

    mensaje = "Umbral de calidad: " + "; ".join(incumplimientos)

    if calidad["accion"] == "fallar":
        raise UmbralCalidadExcedido(mensaje + ". No se cargaron datos.")

    logger.warning(mensaje)
    contexto.setdefault("advertencias", []).append(mensaje)

    return {}
