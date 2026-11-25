
import pandas as pd

from src.configuracion import BASE_DIR, CONFIG


# Obtener las rutas desde la configuración
RAW_DIR = BASE_DIR / CONFIG["rutas"]["raw"]
PROCESSED_DIR = BASE_DIR / CONFIG["rutas"]["processed"]


def consolidar_datos(archivos, raw_dir):
    """
    Lee los archivos CSV de los hospitales y los consolida
    en un único DataFrame.
    """

    lista_hospitales = []

    for archivo, hospital in archivos.items():

        ruta = raw_dir / archivo

        if not ruta.exists():
            raise FileNotFoundError(
                f"No se encontró el archivo: {ruta}"
            )

        df = pd.read_csv(
            ruta,
            dtype={"numero_historia": str}
        )

        df["hospital_origen"] = hospital

        lista_hospitales.append(df)

        print(f"{hospital}: {len(df)} registros cargados")

    if not lista_hospitales:
        raise ValueError("No se encontraron archivos para consolidar.")

    df_consolidado = pd.concat(
        lista_hospitales,
        ignore_index=True
    )

    return df_consolidado


def ejecutar_consolidacion():

    # Construir las fuentes desde config.yaml
    archivos = {
        fuente["archivo"]: fuente["nombre"]
        for fuente in CONFIG["fuentes"]
    }

    df_consolidado = consolidar_datos(
        archivos,
        RAW_DIR
    )

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # Nombre del archivo definido en config.yaml
    nombre_salida = CONFIG["archivos"]["consolidados"]
    ruta_salida = PROCESSED_DIR / nombre_salida

    df_consolidado.to_csv(
        ruta_salida,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nCONSOLIDACIÓN COMPLETADA")
    print(f"Total de registros: {len(df_consolidado)}")
    print(f"Total de columnas: {len(df_consolidado.columns)}")
    print(f"Archivo generado: {ruta_salida}")

    print("\nVista previa:")
    print(df_consolidado.head(10))


if __name__ == "__main__":
    ejecutar_consolidacion()
