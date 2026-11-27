"""
Carga y validación de la configuración del proyecto (config/config.yaml).

La ruta del archivo puede cambiarse con la variable de entorno
ETL_CONFIG_PATH (útil para pruebas de integración, otros ambientes
o para reutilizar el motor con otra configuración).
"""

import os
from pathlib import Path

import yaml

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Ruta por defecto del archivo de configuración
RUTA_CONFIG_POR_DEFECTO = BASE_DIR / "config" / "config.yaml"

# Secciones mínimas que debe tener config.yaml
SECCIONES_REQUERIDAS = (
    "proyecto",
    "fuentes",
    "esquema",
    "rutas",
    "archivos",
    "pipeline",
    "base_datos",
    "logging",
)


def obtener_ruta_config() -> Path:
    """Ruta del archivo de configuración activo."""

    ruta = os.getenv("ETL_CONFIG_PATH")
    return Path(ruta) if ruta else RUTA_CONFIG_POR_DEFECTO


def validar_configuracion(configuracion: dict) -> None:
    """Falla pronto y con un mensaje claro si la configuración está incompleta."""

    faltantes = [s for s in SECCIONES_REQUERIDAS if s not in configuracion]

    if faltantes:
        raise ValueError(
            "config.yaml no contiene las secciones requeridas: "
            + ", ".join(faltantes)
        )

    if not configuracion["fuentes"]:
        raise ValueError("config.yaml debe definir al menos una fuente.")

    if not configuracion["pipeline"].get("tareas"):
        raise ValueError("config.yaml debe definir pipeline.tareas.")

    columna_fuente = configuracion["pipeline"].get("columna_fuente")

    if not columna_fuente:
        raise ValueError(
            "config.yaml debe definir pipeline.columna_fuente: la columna derivada "
            "donde se guarda el nombre de cada fuente (por ejemplo, hospital_origen)."
        )

    columnas_esquema = {
        c.get("nombre"): c for c in configuracion["esquema"].get("columnas", [])
        if isinstance(c, dict)
    }

    if not columnas_esquema.get(columna_fuente, {}).get("derivada"):
        raise ValueError(
            f"pipeline.columna_fuente ('{columna_fuente}') debe existir en el esquema "
            "con 'derivada: true'."
        )

    from src.calidad import validar_config_calidad

    validar_config_calidad(configuracion.get("calidad"))

    clave = configuracion["pipeline"].get("clave_negocio")

    if not isinstance(clave, list) or not clave:
        raise ValueError(
            "config.yaml debe definir pipeline.clave_negocio como una lista de columnas."
        )


def cargar_configuracion(ruta: Path | None = None) -> dict:
    """Carga la configuración general del proyecto desde un archivo YAML."""

    ruta = ruta or obtener_ruta_config()

    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {ruta}")

    with open(ruta, encoding="utf-8") as archivo:
        configuracion = yaml.safe_load(archivo)

    if not isinstance(configuracion, dict):
        raise ValueError(f"El archivo {ruta} no contiene una configuración válida.")

    validar_configuracion(configuracion)

    return configuracion


def resolver_ruta(valor: str) -> Path:
    """Rutas relativas se resuelven desde la raíz del proyecto; absolutas se respetan."""

    ruta = Path(valor)
    return ruta if ruta.is_absolute() else BASE_DIR / ruta


# Configuración disponible para los demás módulos
CONFIG = cargar_configuracion()
