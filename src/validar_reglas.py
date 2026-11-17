
from pathlib import Path
import pandas as pd

# 1. Definir las rutas del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

ARCHIVO_ENTRADA = BASE_DIR / "data" / "processed" / "datos_limpios.csv"
ARCHIVO_VALIDOS = BASE_DIR / "data" / "processed" / "datos_validados.csv"
ARCHIVO_RECHAZADOS = BASE_DIR / "data" / "rejected" / "registros_fuera_reglas.csv"

# 2. Definir las categorías permitidas
ESPECIALIDADES_VALIDAS = [
    "Cirugia",
    "Urologia",
    "Traumatologia"
]

TECNICAS_VALIDAS = [
    "General",
    "Regional",
    "Sedacion"
]

# 3. Leer los datos
df = pd.read_csv(
    ARCHIVO_ENTRADA,
    dtype={"numero_historia": str}
)

# 4. Revisar las reglas de negocio
errores_por_fila = []

for _, fila in df.iterrows():
    errores = []

    if pd.isna(fila["numero_historia"]) or str(fila["numero_historia"]).strip() == "":
        errores.append("Número de historia vacío")

    fecha = pd.to_datetime(fila["fecha"], errors="coerce")
    if pd.isna(fecha):
        errores.append("Fecha inválida")

    edad = pd.to_numeric(fila["edad"], errors="coerce")
    if pd.isna(edad) or not 0 <= edad <= 120:
        errores.append("Edad fuera del rango permitido")

    duracion = pd.to_numeric(fila["duracion_minutos"], errors="coerce")
    if pd.isna(duracion) or duracion <= 0:
        errores.append("Duración inválida")

    if fila["especialidad"] not in ESPECIALIDADES_VALIDAS:
        errores.append("Especialidad no permitida")

    if fila["tecnica_anestesica"] not in TECNICAS_VALIDAS:
        errores.append("Técnica anestésica no permitida")

    if pd.isna(fila["hospital_origen"]) or str(fila["hospital_origen"]).strip() == "":
        errores.append("Hospital de origen vacío")

    errores_por_fila.append("; ".join(errores))

# 5. Clasificar los registros
df["errores_validacion"] = errores_por_fila

df_validos = df[df["errores_validacion"] == ""].drop(
    columns=["errores_validacion"]
)

df_rechazados = df[df["errores_validacion"] != ""]

# 6. Guardar los resultados
df_validos.to_csv(ARCHIVO_VALIDOS, index=False)
df_rechazados.to_csv(ARCHIVO_RECHAZADOS, index=False)

# 7. Mostrar el resumen
print("\nVALIDACIÓN DE REGLAS DE NEGOCIO")
print("--------------------------------")
print(f"Registros originales: {len(df)}")
print(f"Registros válidos: {len(df_validos)}")
print(f"Registros rechazados: {len(df_rechazados)}")

print("\nProceso finalizado.")
