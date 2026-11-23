
from pathlib import Path

import yaml


# Directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Ruta del archivo de configuración
RUTA_CONFIG = BASE_DIR / "config" / "config.yaml"


def cargar_configuracion():
    """
    Carga la configuración general del proyecto desde config.yaml.
    """

    if not RUTA_CONFIG.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de configuración: {RUTA_CONFIG}"
        )

    with open(RUTA_CONFIG, "r", encoding="utf-8") as archivo:
        configuracion = yaml.safe_load(archivo)

    if not isinstance(configuracion, dict):
        raise ValueError(
            "El archivo config.yaml no contiene una configuración válida."
        )

    return configuracion


# Configuración disponible para los demás módulos
CONFIG = cargar_configuracion()
