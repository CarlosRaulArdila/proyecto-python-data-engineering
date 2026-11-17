
import pandas as pd
from pathlib import Path

# Ruta principal del proyecto
PROJECT_DIR = Path.home() / "Documents" / "proyecto_python_data_engineering"

# Carpeta donde guardaremos los archivos originales
RAW_DIR = PROJECT_DIR / "data" / "raw"

# Crear datos ficticios del Hospital 1
hospital_1 = pd.DataFrame({
    "numero_historia": ["001001", "001002", "001003", "001004", "001005"],
    "fecha": ["2026-01-10", "2026-01-11", "2026-01-12", "2026-01-13", "2026-01-14"],
    "edad": [45, 62, 38, 71, 54],
    "especialidad": ["Traumatologia", "Cirugia", "Urologia", "Traumatologia", "Cirugia"],
    "tecnica_anestesica": ["General", "Regional", "General", "Sedacion", "General"],
    "duracion_minutos": [90, 120, 60, 75, 110]
})

# Crear datos ficticios del Hospital 2
hospital_2 = pd.DataFrame({
    "numero_historia": ["002001", "002002", "002003", "002004", "002005"],
    "fecha": ["2026-01-15", "2026-01-16", "2026-01-17", "2026-01-18", "2026-01-19"],
    "edad": [33, 48, None, 67, 59],
    "especialidad": ["Cirugia", "Urologia", "Traumatologia", "Cirugia", "Urologia"],
    "tecnica_anestesica": ["General", "Regional", "General", None, "Sedacion"],
    "duracion_minutos": [80, 95, 130, 70, 100]
})

# Crear datos ficticios del Hospital 3
hospital_3 = pd.DataFrame({
    "numero_historia": ["003001", "003002", "003003", "003004", "003004"],
    "fecha": ["2026-01-20", "2026-01-21", "2026-01-22", "2026-01-23", "2026-01-23"],
    "edad": [29, 56, 43, 64, 64],
    "especialidad": ["Urologia", "Cirugia", "Traumatologia", "Cirugia", "Cirugia"],
    "tecnica_anestesica": ["General", "Sedacion", "Regional", "General", "General"],
    "duracion_minutos": [65, 105, 85, 115, 115]
})

# Guardar los archivos CSV
hospital_1.to_csv(RAW_DIR / "hospital_1.csv", index=False, encoding="utf-8-sig")
hospital_2.to_csv(RAW_DIR / "hospital_2.csv", index=False, encoding="utf-8-sig")
hospital_3.to_csv(RAW_DIR / "hospital_3.csv", index=False, encoding="utf-8-sig")

print("Archivos CSV generados correctamente.")

for archivo in RAW_DIR.glob("*.csv"):
    print(f"Archivo: {archivo.name}")
