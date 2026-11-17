
import pandas as pd
from pathlib import Path

# 1. Definir rutas
PROJECT_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_DIR / "data" / "processed"
    / "datos_consolidados_sin_limpieza.csv"
)

PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
REJECTED_DIR = PROJECT_DIR / "data" / "rejected"

# 2. Crear carpetas si no existen
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
REJECTED_DIR.mkdir(parents=True, exist_ok=True)

# 3. Leer los datos consolidados
df = pd.read_csv(
    INPUT_FILE,
    dtype={"numero_historia": str}
)

print(f"Registros originales: {len(df)}")

# 4. Separar registros incompletos
mascara_incompletos = df.isna().any(axis=1)

df_incompletos = df.loc[mascara_incompletos].copy()

df_completos = df.loc[~mascara_incompletos].copy()

# Guardar registros incompletos
df_incompletos.to_csv(
    REJECTED_DIR / "registros_incompletos.csv",
    index=False,
    encoding="utf-8-sig"
)

# 5. Detectar duplicados exactos
mascara_duplicados = df_completos.duplicated(keep="first")

df_duplicados = df_completos.loc[mascara_duplicados].copy()

# Guardar las repeticiones sobrantes
df_duplicados.to_csv(
    REJECTED_DIR / "registros_duplicados.csv",
    index=False,
    encoding="utf-8-sig"
)

# 6. Conservar una sola copia de cada registro
df_limpio = df_completos.loc[~mascara_duplicados].copy()

# 7. Guardar los datos limpios
df_limpio.to_csv(
    PROCESSED_DIR / "datos_limpios.csv",
    index=False,
    encoding="utf-8-sig"
)

# 8. Mostrar resumen
print("\nPROCESO DE LIMPIEZA COMPLETADO")
print(f"Registros originales: {len(df)}")
print(f"Registros incompletos: {len(df_incompletos)}")
print(f"Duplicados eliminados: {len(df_duplicados)}")
print(f"Registros limpios: {len(df_limpio)}")

print("\nArchivos generados:")
print("- data/processed/datos_limpios.csv")
print("- data/rejected/registros_incompletos.csv")
print("- data/rejected/registros_duplicados.csv")
