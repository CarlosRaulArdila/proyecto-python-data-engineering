
from pathlib import Path
import pandas as pd
from sqlalchemy import text

from conexion_db import engine

# 1. Localizar el archivo validado
BASE_DIR = Path(__file__).resolve().parent.parent

ARCHIVO_ENTRADA = (
    BASE_DIR / "data" / "processed" / "datos_validados.csv"
)

# 2. Leer los datos
df = pd.read_csv(
    ARCHIVO_ENTRADA,
    dtype={"numero_historia": str},
    parse_dates=["fecha"]
)

print(f"Registros preparados para cargar: {len(df)}")

# 3. Cargar los datos en PostgreSQL
try:
    with engine.begin() as connection:

        # Limpiar la tabla antes de realizar la carga completa
        connection.execute(
            text("TRUNCATE TABLE hospital_registros RESTART IDENTITY")
        )

        # Insertar los registros
        df.to_sql(
            name="hospital_registros",
            con=connection,
            schema="public",
            if_exists="append",
            index=False,
            method="multi"
        )

    print("CARGA COMPLETADA CORRECTAMENTE")
    print(f"Registros insertados: {len(df)}")

except Exception as error:
    print("ERROR DURANTE LA CARGA")
    print(error)

finally:
    engine.dispose()
