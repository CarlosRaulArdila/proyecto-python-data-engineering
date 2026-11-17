
from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# 1. Localizar el archivo .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# 2. Obtener las credenciales
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# 3. Comprobar que las variables existen
if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
    raise ValueError("Faltan variables de conexión en el archivo .env")

# 4. Crear la conexión
DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(DATABASE_URL)

# 5. Probar la conexión
try:
    with engine.connect() as connection:
        resultado = connection.execute(text("SELECT version()"))
        version = resultado.scalar()

        print("CONEXIÓN EXITOSA")
        print("Base de datos:", DB_NAME)
        print("PostgreSQL:", version)

except Exception as error:
    print("ERROR DE CONEXIÓN")
    print(error)

finally:
    engine.dispose()
