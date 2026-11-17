
import pandas as pd
from pathlib import Path

# Directorios del proyecto
PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"

# Buscar todos los archivos CSV
archivos = list(RAW_DIR.glob("*.csv"))

# Inspeccionar cada archivo
for archivo in archivos:

    print("\n" + "=" * 50)
    print(f"HOSPITAL: {archivo.name}")
    print("=" * 50)

    # Leer archivo CSV
    df = pd.read_csv(archivo, dtype={"numero_historia": str})

    # Mostrar dimensiones
    print(f"\nNúmero de registros: {df.shape[0]}")
    print(f"Número de columnas: {df.shape[1]}")

    # Mostrar nombres de columnas
    print("\nColumnas:")
    print(df.columns.tolist())

    # Mostrar valores vacíos
    print("\nValores vacíos por columna:")
    print(df.isnull().sum())

    # Mostrar registros duplicados
    print(f"\nRegistros duplicados: {df.duplicated().sum()}")

    # Mostrar primeras filas
    print("\nPrimeros registros:")
    print(df.head())
