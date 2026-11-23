
import pandas as pd

from src.configuracion import BASE_DIR, CONFIG


# Obtener rutas desde config.yaml
PROCESSED_DIR = BASE_DIR / CONFIG["rutas"]["processed"]
REJECTED_DIR = BASE_DIR / CONFIG["rutas"]["rejected"]

# Obtener nombres de archivos desde config.yaml
INPUT_FILE = PROCESSED_DIR / CONFIG["archivos"]["consolidados"]

OUTPUT_LIMPIOS = PROCESSED_DIR / CONFIG["archivos"]["limpios"]
OUTPUT_INCOMPLETOS = REJECTED_DIR / CONFIG["archivos"]["incompletos"]
OUTPUT_DUPLICADOS = REJECTED_DIR / CONFIG["archivos"]["duplicados"]


def limpiar_datos(df):
    """
    Separa los registros incompletos, detecta duplicados
    exactos y devuelve los registros limpios.
    """

    # Separar registros incompletos
    mascara_incompletos = df.isna().any(axis=1)

    df_incompletos = df.loc[mascara_incompletos].copy()
    df_completos = df.loc[~mascara_incompletos].copy()

    # Detectar duplicados exactos
    mascara_duplicados = df_completos.duplicated(keep="first")

    df_duplicados = df_completos.loc[mascara_duplicados].copy()

    # Conservar una sola copia de cada registro
    df_limpio = df_completos.loc[~mascara_duplicados].copy()

    return df_limpio, df_incompletos, df_duplicados


def ejecutar_limpieza():

    # Crear carpetas si no existen
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)

    # Verificar que exista el archivo de entrada
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo consolidado: {INPUT_FILE}"
        )

    # Leer datos consolidados
    df = pd.read_csv(
        INPUT_FILE,
        dtype={"numero_historia": str}
    )

    print(f"Registros originales: {len(df)}")

    # Aplicar limpieza
    df_limpio, df_incompletos, df_duplicados = limpiar_datos(df)

    # Guardar registros incompletos
    df_incompletos.to_csv(
        OUTPUT_INCOMPLETOS,
        index=False,
        encoding="utf-8-sig"
    )

    # Guardar duplicados
    df_duplicados.to_csv(
        OUTPUT_DUPLICADOS,
        index=False,
        encoding="utf-8-sig"
    )

    # Guardar datos limpios
    df_limpio.to_csv(
        OUTPUT_LIMPIOS,
        index=False,
        encoding="utf-8-sig"
    )

    # Mostrar resumen
    print("\nPROCESO DE LIMPIEZA COMPLETADO")
    print(f"Registros originales: {len(df)}")
    print(f"Registros incompletos: {len(df_incompletos)}")
    print(f"Duplicados eliminados: {len(df_duplicados)}")
    print(f"Registros limpios: {len(df_limpio)}")

    print("\nArchivos generados:")
    print(f"- {OUTPUT_LIMPIOS}")
    print(f"- {OUTPUT_INCOMPLETOS}")
    print(f"- {OUTPUT_DUPLICADOS}")


if __name__ == "__main__":
    ejecutar_limpieza()
