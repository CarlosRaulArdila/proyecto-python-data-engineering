"""
Registro de auditoría de las ejecuciones del pipeline (public.etl_auditoria).

La tabla se define en config.yaml (base_datos.tabla_auditoria) y se crea
con la migración sql/migraciones/V002__crear_etl_auditoria.sql.
"""

import uuid

from sqlalchemy import text

from src.conexion_db import obtener_engine
from src.configuracion import CONFIG
from src.sql_utils import nombre_tabla

# Tabla de auditoría desde config.yaml (base_datos.esquema / tabla_auditoria)
TABLA_AUDITORIA = nombre_tabla(
    CONFIG["base_datos"]["esquema"],
    CONFIG["base_datos"].get("tabla_auditoria", "etl_auditoria"),
)

ESTADO_EN_PROCESO = "EN_PROCESO"
ESTADO_EXITOSO = "EXITOSO"
ESTADO_FALLIDO = "FALLIDO"
ESTADO_PARCIAL = "PARCIAL"

ESTADOS_FINALES = {ESTADO_EXITOSO, ESTADO_FALLIDO, ESTADO_PARCIAL}


def registrar_inicio(
    run_id=None,
    proyecto_id=None,
    pipeline_id=None,
    orquestador="manual",
    version_pipeline=None,
    ambiente=None,
    archivo_log=None,
):
    """Inserta la fila de la ejecución con estado EN_PROCESO y devuelve su id."""

    if run_id is None:
        run_id = uuid.uuid4()

    consulta = text(f"""
        INSERT INTO {TABLA_AUDITORIA} (
            fecha_inicio,
            estado,
            run_id,
            proyecto_id,
            pipeline_id,
            orquestador,
            version_pipeline,
            ambiente,
            archivo_log
        )
        VALUES (
            CURRENT_TIMESTAMP,
            :estado,
            :run_id,
            :proyecto_id,
            :pipeline_id,
            :orquestador,
            :version_pipeline,
            :ambiente,
            :archivo_log
        )
        RETURNING id;
    """)

    with obtener_engine().begin() as conexion:
        resultado = conexion.execute(
            consulta,
            {
                "estado": ESTADO_EN_PROCESO,
                "run_id": str(run_id),
                "proyecto_id": proyecto_id,
                "pipeline_id": pipeline_id,
                "orquestador": orquestador,
                "version_pipeline": version_pipeline,
                "ambiente": ambiente,
                "archivo_log": archivo_log,
            },
        )

        return resultado.scalar_one()


def registrar_fin(
    id_ejecucion,
    estado,
    registros_extraidos=0,
    registros_limpios=0,
    registros_rechazados=0,
    operaciones_bd=0,
    duracion_segundos=0,
    mensaje_error=None,
    advertencias=None,
):
    """Cierra la fila de la ejecución con su estado final y sus métricas."""

    if estado not in ESTADOS_FINALES:
        raise ValueError(
            f"Estado final no válido: {estado}. "
            f"Valores permitidos: {sorted(ESTADOS_FINALES)}"
        )

    consulta = text(f"""
        UPDATE {TABLA_AUDITORIA}
        SET
            fecha_fin = CURRENT_TIMESTAMP,
            estado = :estado,
            registros_extraidos = :registros_extraidos,
            registros_limpios = :registros_limpios,
            registros_rechazados = :registros_rechazados,
            operaciones_bd = :operaciones_bd,
            duracion_segundos = :duracion_segundos,
            mensaje_error = :mensaje_error,
            advertencias = :advertencias
        WHERE id = :id_ejecucion;
    """)

    with obtener_engine().begin() as conexion:
        resultado = conexion.execute(
            consulta,
            {
                "id_ejecucion": id_ejecucion,
                "estado": estado,
                "registros_extraidos": registros_extraidos,
                "registros_limpios": registros_limpios,
                "registros_rechazados": registros_rechazados,
                "operaciones_bd": operaciones_bd,
                "duracion_segundos": round(float(duracion_segundos), 3),
                "mensaje_error": mensaje_error,
                "advertencias": advertencias,
            },
        )

        if resultado.rowcount != 1:
            raise ValueError(f"No se encontró la ejecución con ID {id_ejecucion}")
