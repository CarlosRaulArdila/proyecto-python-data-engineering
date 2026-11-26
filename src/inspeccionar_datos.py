"""
Perfilado rápido de los archivos CSV de la carpeta raw.

Uso:
    python -m src.inspeccionar_datos
"""

import pandas as pd

from src.configuracion import CONFIG, resolver_ruta

RAW_DIR = resolver_ruta(CONFIG["rutas"]["raw"])


def inspeccionar(raw_dir=RAW_DIR):
    for archivo in sorted(raw_dir.glob("*.csv")):
        print("\n" + "=" * 50)
        print(f"ARCHIVO: {archivo.name}")
        print("=" * 50)

        df = pd.read_csv(archivo, dtype=str, encoding="utf-8-sig")

        print(f"\nNúmero de registros: {df.shape[0]}")
        print(f"Número de columnas: {df.shape[1]}")

        print("\nColumnas:")
        print(df.columns.tolist())

        print("\nValores vacíos por columna:")
        print(df.isnull().sum())

        print(f"\nRegistros duplicados: {df.duplicated().sum()}")

        print("\nPrimeros registros:")
        print(df.head())


if __name__ == "__main__":
    inspeccionar()
