
from sqlalchemy import text

try:
    from src.conexion_db import engine
except ModuleNotFoundError:
    from conexion_db import engine


def registrar_inicio():

    consulta = text("""
        INSERT INTO public.etl_auditoria (
            fecha_inicio,
            estado
        )
        VALUES (
            CURRENT_TIMESTAMP,
            'EN_PROCESO'
        )
        RETURNING id;
    """)

    with engine.begin() as conexion:

        resultado = conexion.execute(consulta)

        id_ejecucion = resultado.scalar_one()

    return id_ejecucion


def registrar_fin(
    id_ejecucion,
    estado,
    registros_extraidos=0,
    registros_limpios=0,
    registros_rechazados=0,
    operaciones_bd=0,
    duracion_segundos=0,
    mensaje_error=None
):

    consulta = text("""
        UPDATE public.etl_auditoria
        SET
            fecha_fin = CURRENT_TIMESTAMP,
            estado = :estado,
            registros_extraidos = :registros_extraidos,
            registros_limpios = :registros_limpios,
            registros_rechazados = :registros_rechazados,
            operaciones_bd = :operaciones_bd,
            duracion_segundos = :duracion_segundos,
            mensaje_error = :mensaje_error
        WHERE id = :id_ejecucion;
    """)

    with engine.begin() as conexion:

        resultado = conexion.execute(
            consulta,
            {
                "id_ejecucion": id_ejecucion,
                "estado": estado,
                "registros_extraidos": registros_extraidos,
                "registros_limpios": registros_limpios,
                "registros_rechazados": registros_rechazados,
                "operaciones_bd": operaciones_bd,
                "duracion_segundos": duracion_segundos,
                "mensaje_error": mensaje_error
            }
        )

        if resultado.rowcount != 1:
            raise ValueError(
                f"No se encontró la ejecución con ID {id_ejecucion}"
            )
