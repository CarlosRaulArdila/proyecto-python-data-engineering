
import pandas as pd
from sqlalchemy import text

from src.configuracion import BASE_DIR, CONFIG

try:
    from src.conexion_db import engine
except ModuleNotFoundError:
    from conexion_db import engine


# Obtener configuración desde config.yaml
PROCESSED_DIR = BASE_DIR / CONFIG["rutas"]["processed"]

RUTA_ARCHIVO = (
    PROCESSED_DIR / CONFIG["archivos"]["validados"]
)

ESQUEMA_DESTINO = CONFIG["base_datos"]["esquema"]
TABLA_DESTINO = CONFIG["base_datos"]["tabla_destino"]

TABLA_CONFIGURADA = f"{ESQUEMA_DESTINO}.{TABLA_DESTINO}"


# Tablas permitidas para la carga incremental
TABLAS_PERMITIDAS = {
    TABLA_CONFIGURADA,
    "pruebas_etl.hospital_registros"
}


# Preparar los datos
def preparar_datos(ruta_archivo):

    if not ruta_archivo.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo validado: {ruta_archivo}"
        )

    df = pd.read_csv(
        ruta_archivo,
        dtype={"numero_historia": str}
    )

    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date

    return df


# Construir la consulta SQL
def construir_consulta(tabla):

    if tabla not in TABLAS_PERMITIDAS:
        raise ValueError(f"Tabla no permitida: {tabla}")

    consulta = text(f"""
        INSERT INTO {tabla} AS destino (
            numero_historia,
            fecha,
            edad,
            especialidad,
            tecnica_anestesica,
            duracion_minutos,
            hospital_origen
        )
        VALUES (
            :numero_historia,
            :fecha,
            :edad,
            :especialidad,
            :tecnica_anestesica,
            :duracion_minutos,
            :hospital_origen
        )
        ON CONFLICT (
            numero_historia,
            fecha,
            hospital_origen
        )
        DO UPDATE SET
            edad = EXCLUDED.edad,
            especialidad = EXCLUDED.especialidad,
            tecnica_anestesica = EXCLUDED.tecnica_anestesica,
            duracion_minutos = EXCLUDED.duracion_minutos
        WHERE
            destino.edad IS DISTINCT FROM EXCLUDED.edad
            OR destino.especialidad IS DISTINCT FROM EXCLUDED.especialidad
            OR destino.tecnica_anestesica IS DISTINCT FROM EXCLUDED.tecnica_anestesica
            OR destino.duracion_minutos IS DISTINCT FROM EXCLUDED.duracion_minutos;
    """)

    return consulta


# Ejecutar la carga incremental
def cargar_incremental(
    df,
    conexion,
    tabla=TABLA_CONFIGURADA
):

    registros = df.to_dict(orient="records")

    consulta = construir_consulta(tabla)

    resultado = conexion.execute(consulta, registros)

    return resultado.rowcount


# Coordinar el proceso completo
def ejecutar_carga_incremental():

    df = preparar_datos(RUTA_ARCHIVO)

    with engine.begin() as conexion:

        operaciones = cargar_incremental(
            df,
            conexion
        )

    print(f"Registros procesados: {len(df)}")
    print(
        "Operaciones realizadas (insertados o actualizados): "
        f"{operaciones}"
    )
    print(f"Tabla de destino: {TABLA_CONFIGURADA}")
    print("Carga incremental finalizada.")


if __name__ == "__main__":
    ejecutar_carga_incremental()
