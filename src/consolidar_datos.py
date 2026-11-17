
import pandas as pd
from pathlib import Path

# 1. Definir las rutas del proyecto
PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

# 2. Identificar los archivos de los hospitales
archivos = {
    "hospital_1.csv": "Hospital 1",
    "hospital_2.csv": "Hospital 2",
    "hospital_3.csv": "Hospital 3"
}

# 3. Crear una lista para almacenar los DataFrames
lista_hospitales = []

# 4. Leer y consolidar cada archivo
for archivo, hospital in archivos.items():

    ruta = RAW_DIR / archivo

    df = pd.read_csv(
        ruta,
        dtype={"numero_historia": str}
    )

    # Añadir el hospital de procedencia
    df["hospital_origen"] = hospital

    # Agregar el DataFrame a la lista
    lista_hospitales.append(df)

    print(f"{hospital}: {len(df)} registros cargados")

# 5. Unir todos los DataFrames
df_consolidado = pd.concat(
    lista_hospitales,
    ignore_index=True
)

# 6. Crear la carpeta de destino si no existe
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# 7. Guardar el archivo consolidado
ruta_salida = PROCESSED_DIR / "datos_consolidados_sin_limpieza.csv"

df_consolidado.to_csv(
    ruta_salida,
    index=False,
    encoding="utf-8-sig"
)

# 8. Mostrar resultados
print("\nCONSOLIDACIÓN COMPLETADA")
print(f"Total de registros: {len(df_consolidado)}")
print(f"Total de columnas: {len(df_consolidado.columns)}")
print(f"Archivo generado: {ruta_salida}")

print("\nVista previa:")
print(df_consolidado.head(10))
