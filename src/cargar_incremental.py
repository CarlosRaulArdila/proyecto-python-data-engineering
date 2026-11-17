
import pandas as pd
from sqlalchemy import text
from conexion_db import engine

# 1. Leer el archivo CSV
ruta_archivo = "data/processed/datos_validados.csv"

df = pd.read_csv(
    ruta_archivo,
    dtype={"numero_historia": str}
)

# 2. Convertir la fecha al formato adecuado
df["fecha"] = pd.to_datetime(df["fecha"]).dt.date

# 3. Preparar la consulta SQL
consulta = text("""
    INSERT INTO public.hospital_registros (
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
    hospital_registros.edad IS DISTINCT FROM EXCLUDED.edad
    OR hospital_registros.especialidad IS DISTINCT FROM EXCLUDED.especialidad
    OR hospital_registros.tecnica_anestesica IS DISTINCT FROM EXCLUDED.tecnica_anestesica
    OR hospital_registros.duracion_minutos IS DISTINCT FROM EXCLUDED.duracion_minutos;
""")

# 4. Insertar únicamente registros nuevos
registros = df.to_dict(orient="records")

with engine.begin() as conexion:
    resultado = conexion.execute(consulta, registros)

print(f"Registros procesados: {len(registros)}")
print(f"Operaciones realizadas (insertados o actualizados): {resultado.rowcount}")
print("Carga incremental finalizada.")
