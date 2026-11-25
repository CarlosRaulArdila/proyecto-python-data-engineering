
import pandas as pd

from src.configuracion import BASE_DIR, CONFIG


# Obtener rutas desde config.yaml
PROCESSED_DIR = BASE_DIR / CONFIG["rutas"]["processed"]
REJECTED_DIR = BASE_DIR / CONFIG["rutas"]["rejected"]

# Obtener nombres de archivos desde config.yaml
ARCHIVO_ENTRADA = PROCESSED_DIR / CONFIG["archivos"]["limpios"]
ARCHIVO_VALIDOS = PROCESSED_DIR / CONFIG["archivos"]["validados"]
ARCHIVO_RECHAZADOS = REJECTED_DIR / CONFIG["archivos"]["fuera_reglas"]


# Categorías permitidas
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


def validar_datos(df):

    errores_por_fila = []

    for _, fila in df.iterrows():
        errores = []

        # Validar número de historia
        if (
            pd.isna(fila["numero_historia"])
            or str(fila["numero_historia"]).strip() == ""
        ):
            errores.append("Número de historia vacío")

        # Validar fecha
        fecha = pd.to_datetime(fila["fecha"], errors="coerce")

        if pd.isna(fecha):
            errores.append("Fecha inválida")

        # Validar edad
        edad = pd.to_numeric(fila["edad"], errors="coerce")

        if pd.isna(edad) or not 0 <= edad <= 120:
            errores.append("Edad fuera del rango permitido")

        # Validar duración
        duracion = pd.to_numeric(
            fila["duracion_minutos"],
            errors="coerce"
        )

        if pd.isna(duracion) or duracion <= 0:
            errores.append("Duración inválida")

        # Validar especialidad
        if fila["especialidad"] not in ESPECIALIDADES_VALIDAS:
            errores.append("Especialidad no permitida")

        # Validar técnica anestésica
        if fila["tecnica_anestesica"] not in TECNICAS_VALIDAS:
            errores.append("Técnica anestésica no permitida")

        # Validar hospital de origen
        if (
            pd.isna(fila["hospital_origen"])
            or str(fila["hospital_origen"]).strip() == ""
        ):
            errores.append("Hospital de origen vacío")

        errores_por_fila.append("; ".join(errores))

    # Clasificar registros
    df_resultado = df.copy()
    df_resultado["errores_validacion"] = errores_por_fila

    df_validos = df_resultado[
        df_resultado["errores_validacion"] == ""
    ].drop(columns=["errores_validacion"])

    df_rechazados = df_resultado[
        df_resultado["errores_validacion"] != ""
    ].copy()

    return df_validos, df_rechazados


def ejecutar_validacion():

    # Crear carpetas si no existen
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)

    # Verificar archivo de entrada
    if not ARCHIVO_ENTRADA.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de datos limpios: {ARCHIVO_ENTRADA}"
        )

    # Leer datos limpios
    df = pd.read_csv(
        ARCHIVO_ENTRADA,
        dtype={"numero_historia": str}
    )

    # Aplicar reglas de negocio
    df_validos, df_rechazados = validar_datos(df)

    # Guardar resultados
    df_validos.to_csv(
        ARCHIVO_VALIDOS,
        index=False,
        encoding="utf-8-sig"
    )

    df_rechazados.to_csv(
        ARCHIVO_RECHAZADOS,
        index=False,
        encoding="utf-8-sig"
    )

    # Mostrar resumen
    print("\nVALIDACIÓN DE REGLAS DE NEGOCIO")
    print("--------------------------------")
    print(f"Registros originales: {len(df)}")
    print(f"Registros válidos: {len(df_validos)}")
    print(f"Registros rechazados: {len(df_rechazados)}")

    print("\nProceso finalizado.")
    print(f"Archivo de válidos: {ARCHIVO_VALIDOS}")
    print(f"Archivo de rechazados: {ARCHIVO_RECHAZADOS}")


if __name__ == "__main__":
    ejecutar_validacion()
