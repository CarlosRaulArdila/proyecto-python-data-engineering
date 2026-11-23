
from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text, URL


# 1. Localizar el archivo .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# 2. Crear el motor de conexión
def crear_engine():

    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")

    if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
        raise ValueError(
            "Faltan variables de conexión en el archivo .env"
        )

    DATABASE_URL = URL.create(
        drivername="postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=int(DB_PORT),
        database=DB_NAME
    )

    return create_engine(
        DATABASE_URL,
        pool_pre_ping=True
    )


# 3. Crear el motor sin conectarse automáticamente
engine = crear_engine()


# 4. Función independiente para comprobar la conexión
def probar_conexion():

    try:
        with engine.connect() as connection:

            resultado = connection.execute(
                text("SELECT version()")
            )

            version = resultado.scalar()

            print("CONEXIÓN EXITOSA")
            print("Base de datos:", engine.url.database)
            print("PostgreSQL:", version)

            return True

    except Exception as error:

        print("ERROR DE CONEXIÓN")
        print(error)

        return False


# 5. Probar la conexión únicamente al ejecutar este archivo
if __name__ == "__main__":
    probar_conexion()
