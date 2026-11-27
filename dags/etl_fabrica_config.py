"""
Lógica de la fábrica de pipelines (sin dependencias de Airflow).

Lee la configuración de cada pipeline del proyecto y la convierte en una
especificación de orquestación. Se usa desde fabrica_pipelines_etl.py y
desde las pruebas (por eso no importa nada de Airflow).

Pipelines que se descubren (rutas relativas a la raíz de configuraciones):
    config/config.yaml          -> pipeline principal
    pipelines/<nombre>/config.yaml  (se ignoran las carpetas que empiezan por "_")

Sección opcional en cada config.yaml:

    orquestacion:
      activo: true                       # false: no se crea el DAG
      dag_id: "hospital_etl_pipeline"    # por defecto, pipeline.id
      horario: "0 6 * * *"               # cron; null = solo manual
      zona_horaria: "America/Bogota"
      reintentos_migraciones: 2
      minutos_entre_reintentos: 5
      tiempo_maximo_minutos: 15
      conexion_airflow: "hospital_dw_etl"
      etiquetas: ["hospital"]
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

VERSION_MOTOR = "2.1.0"

PATRON_DAG_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,200}$")
PATRON_CRON = re.compile(r"^(@(hourly|daily|weekly|monthly|yearly))$|^(\S+\s+){4}\S+$")
PREFIJOS_PERMITIDOS = ("data/", "logs/")

CLAVES_ORQUESTACION = {
    "activo",
    "dag_id",
    "horario",
    "zona_horaria",
    "reintentos_migraciones",
    "minutos_entre_reintentos",
    "tiempo_maximo_minutos",
    "conexion_airflow",
    "etiquetas",
}


@dataclass(frozen=True)
class EspecificacionDag:
    dag_id: str
    descripcion: str
    ruta_config: str  # relativa a /app dentro de la imagen ETL
    horario: str | None
    zona_horaria: str
    reintentos_migraciones: int
    minutos_entre_reintentos: int
    tiempo_maximo_minutos: int
    conexion_airflow: str
    ambiente: str
    rutas_raw: tuple[str, ...]
    etiquetas: tuple[str, ...] = field(default_factory=tuple)


def descubrir_configuraciones(raiz: Path) -> list[tuple[str, dict]]:
    """Devuelve [(ruta_relativa, config)] de todos los pipelines encontrados."""

    rutas = []
    principal = raiz / "config" / "config.yaml"

    if principal.exists():
        rutas.append(principal)

    for ruta in sorted((raiz / "pipelines").glob("*/config.yaml")):
        if not ruta.parent.name.startswith("_"):
            rutas.append(ruta)

    resultado = []

    for ruta in rutas:
        with open(ruta, encoding="utf-8") as archivo:
            resultado.append((ruta.relative_to(raiz).as_posix(), yaml.safe_load(archivo)))

    return resultado


def _ruta_bajo_proyecto(valor: str, nombre: str, dag_id: str) -> str:
    ruta = str(valor).replace("\\", "/").rstrip("/")
    dentro = any(ruta == p.rstrip("/") or ruta.startswith(p) for p in PREFIJOS_PERMITIDOS)

    if ruta.startswith("/") or ".." in ruta.split("/") or not dentro:
        raise ValueError(
            f"[{dag_id}] rutas.{nombre} = {valor!r}: para ejecutarse en Airflow debe ser "
            f"relativa y estar dentro de {', '.join(PREFIJOS_PERMITIDOS)}"
        )

    return ruta.rstrip("/")


def especificacion(ruta_config: str, config: dict) -> EspecificacionDag | None:
    """Convierte un config.yaml en la especificación de su DAG (None si está inactivo)."""

    orquestacion = config.get("orquestacion") or {}
    desconocidas = set(orquestacion) - CLAVES_ORQUESTACION

    dag_id = orquestacion.get("dag_id") or config["pipeline"]["id"]

    if desconocidas:
        raise ValueError(
            f"[{dag_id}] Claves desconocidas en 'orquestacion': {sorted(desconocidas)}"
        )

    if not orquestacion.get("activo", True):
        return None

    if not PATRON_DAG_ID.match(dag_id):
        raise ValueError(f"dag_id inválido: {dag_id!r}")

    horario = orquestacion.get("horario")

    if horario is not None and not PATRON_CRON.match(str(horario).strip()):
        raise ValueError(
            f"[{dag_id}] horario inválido: {horario!r}. Use una expresión cron de 5 campos "
            "(por ejemplo '0 6 * * *') o null para ejecución manual."
        )

    rutas = config["rutas"]

    for nombre in ("processed", "rejected", "logs"):
        _ruta_bajo_proyecto(rutas[nombre], nombre, dag_id)

    proyecto = config.get("proyecto", {})

    return EspecificacionDag(
        dag_id=dag_id,
        descripcion=f"Pipeline ETL {proyecto.get('nombre', dag_id)} ({ruta_config})",
        ruta_config=ruta_config,
        horario=str(horario).strip() if horario is not None else None,
        zona_horaria=orquestacion.get("zona_horaria", "America/Bogota"),
        reintentos_migraciones=int(orquestacion.get("reintentos_migraciones", 2)),
        minutos_entre_reintentos=int(orquestacion.get("minutos_entre_reintentos", 5)),
        tiempo_maximo_minutos=int(orquestacion.get("tiempo_maximo_minutos", 15)),
        conexion_airflow=orquestacion.get("conexion_airflow", "hospital_dw_etl"),
        ambiente=proyecto.get("entorno", "desarrollo"),
        rutas_raw=(_ruta_bajo_proyecto(rutas["raw"], "raw", dag_id),),
        etiquetas=tuple(orquestacion.get("etiquetas", [])),
    )


def especificaciones(raiz: Path) -> tuple[list[EspecificacionDag], list[str]]:
    """
    Especificaciones válidas y lista de errores. Un pipeline mal configurado
    no impide crear los DAG de los demás.
    """

    validas, errores, vistos = [], [], set()

    for ruta, config in descubrir_configuraciones(raiz):
        try:
            spec = especificacion(ruta, config)
        except Exception as error:  # noqa: BLE001 - se informa y se continúa
            errores.append(f"{ruta}: {error}")
            continue

        if spec is None:
            continue

        if spec.dag_id in vistos:
            errores.append(f"{ruta}: dag_id duplicado {spec.dag_id!r}")
            continue

        vistos.add(spec.dag_id)
        validas.append(spec)

    return validas, errores


def es_fallo_reportado_por_el_pipeline(task_id: str, excepcion: BaseException | None) -> bool:
    """
    True si la tarea falló porque el pipeline terminó con código 1: en ese
    caso el propio pipeline ya registró la auditoría y envió su alerta, y
    Airflow no debe duplicarla. Cualquier otro fallo (imagen inexistente,
    contenedor que no arranca, tiempo agotado, migraciones...) sí se avisa.
    """

    return (
        task_id == "ejecutar_pipeline_etl"
        and excepcion is not None
        and "'StatusCode': 1," in str(excepcion)
    )
