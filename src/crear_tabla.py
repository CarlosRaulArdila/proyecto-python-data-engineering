
from sqlalchemy import text

from conexion_db import engine

sql = """
CREATE TABLE IF NOT EXISTS hospital_registros (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_historia VARCHAR(20) NOT NULL,
    fecha DATE NOT NULL,
    edad INTEGER NOT NULL,
    especialidad VARCHAR(50) NOT NULL,
    tecnica_anestesica VARCHAR(50) NOT NULL,
    duracion_minutos INTEGER NOT NULL,
    hospital_origen VARCHAR(100) NOT NULL
);
"""

try:
    with engine.begin() as connection:
        connection.execute(text(sql))

    print("TABLA CREADA CORRECTAMENTE")
    print("Tabla: hospital_registros")

except Exception as error:
    print("ERROR AL CREAR LA TABLA")
    print(error)

finally:
    engine.dispose()
