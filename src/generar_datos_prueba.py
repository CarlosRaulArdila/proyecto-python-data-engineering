
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

ARCHIVO_SALIDA = BASE_DIR / "data" / "raw" / "datos_prueba.csv"

# Registros sintéticos: dos correctos y tres con errores
datos = [
    {
        "numero_historia": "TEST001",
        "fecha": "2026-02-01",
        "edad": 45,
        "especialidad": "Cirugia",
        "tecnica_anestesica": "General",
        "duracion_minutos": 90,
        "hospital_origen": "Hospital Prueba"
    },
    {
        "numero_historia": "TEST002",
        "fecha": "2026-02-02",
        "edad": 150,
        "especialidad": "Cirugia",
        "tecnica_anestesica": "General",
        "duracion_minutos": 90,
        "hospital_origen": "Hospital Prueba"
    },
    {
        "numero_historia": "TEST003",
        "fecha": "2026-02-03",
        "edad": 40,
        "especialidad": "Urologia",
        "tecnica_anestesica": "Regional",
        "duracion_minutos": -20,
        "hospital_origen": "Hospital Prueba"
    },
    {
        "numero_historia": "TEST004",
        "fecha": "2026-02-04",
        "edad": 55,
        "especialidad": "Cardiologia",
        "tecnica_anestesica": "General",
        "duracion_minutos": 80,
        "hospital_origen": "Hospital Prueba"
    },
    {
        "numero_historia": "TEST005",
        "fecha": "2026-02-05",
        "edad": 60,
        "especialidad": "Traumatologia",
        "tecnica_anestesica": "Sedacion",
        "duracion_minutos": 100,
        "hospital_origen": "Hospital Prueba"
    }
]

df = pd.DataFrame(datos)

df.to_csv(ARCHIVO_SALIDA, index=False)

print("Archivo de prueba generado correctamente.")
print(f"Registros creados: {len(df)}")
print(f"Ubicación: {ARCHIVO_SALIDA}")
