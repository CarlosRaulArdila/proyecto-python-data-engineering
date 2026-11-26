"""
Esquema (contrato de datos) declarado en config.yaml.

Define, en un solo lugar, las columnas que maneja el pipeline, su tipo
y si son obligatorias. Los módulos del motor lo usan para leer, limpiar
y cargar los datos sin tener nombres de columnas escritos en el código.

Ejemplo en config.yaml:

    esquema:
      columnas:
        - nombre: "numero_historia"
          tipo: "texto"
          etiqueta: "Número de historia"   # usado en los mensajes
          longitud_max: 20
        - nombre: "edad"
          tipo: "entero"
        - nombre: "hospital_origen"
          tipo: "texto"
          derivada: true      # la añade el pipeline, no viene en la fuente

Tipos admitidos: texto, entero, decimal, fecha, booleano.
"""

import logging
from dataclasses import dataclass

import pandas as pd

from src.sql_utils import validar_identificador

logger = logging.getLogger(__name__)

TIPOS_ADMITIDOS = {"texto", "entero", "decimal", "fecha", "booleano"}

CLAVES_COLUMNA = {
    "nombre",
    "tipo",
    "etiqueta",
    "obligatoria",
    "derivada",
    "longitud_max",
    "descripcion",
}


@dataclass(frozen=True)
class Columna:
    nombre: str
    tipo: str
    obligatoria: bool = True
    derivada: bool = False
    longitud_max: int | None = None
    descripcion: str | None = None
    etiqueta: str | None = None  # nombre legible para los mensajes de validación


@dataclass(frozen=True)
class Esquema:
    columnas: tuple[Columna, ...]

    # ---------------------------------------------------------------
    # Consultas
    # ---------------------------------------------------------------

    @property
    def nombres(self) -> list[str]:
        return [c.nombre for c in self.columnas]

    @property
    def obligatorias(self) -> list[str]:
        return [c.nombre for c in self.columnas if c.obligatoria]

    @property
    def de_fuente(self) -> list[str]:
        """Columnas que deben venir en cada archivo de origen."""
        return [c.nombre for c in self.columnas if not c.derivada]

    def de_tipo(self, *tipos: str) -> list[str]:
        return [c.nombre for c in self.columnas if c.tipo in tipos]

    def columna(self, nombre: str) -> Columna:
        for columna in self.columnas:
            if columna.nombre == nombre:
                return columna
        raise KeyError(f"La columna '{nombre}' no está en el esquema")

    def dtypes_lectura(self) -> dict[str, type]:
        """
        Tipos para pd.read_csv. Solo se fuerzan las columnas de texto
        (para conservar ceros iniciales como en '001001'); el resto se
        convierte y valida después, para poder informar qué filas fallan.
        """
        return {nombre: str for nombre in self.de_tipo("texto")}

    # ---------------------------------------------------------------
    # Verificaciones
    # ---------------------------------------------------------------

    def ajustar_columnas_fuente(self, df: pd.DataFrame, origen: str) -> pd.DataFrame:
        """
        Comprueba que una fuente tenga todas las columnas del esquema
        (salvo las derivadas) y descarta, avisando, las que sobran.
        Devuelve las columnas en el orden del esquema.
        """

        faltantes = [c for c in self.de_fuente if c not in df.columns]

        if faltantes:
            raise ValueError(
                f"La fuente '{origen}' no tiene las columnas requeridas por "
                f"el esquema: {faltantes}. Columnas encontradas: {list(df.columns)}"
            )

        sobrantes = [c for c in df.columns if c not in self.de_fuente]

        if sobrantes:
            logger.warning(
                "La fuente '%s' trae columnas que no están en el esquema y se "
                "descartan: %s",
                origen,
                sobrantes,
            )

        return df[self.de_fuente]

    def validar_clave(self, clave: list[str]) -> None:
        faltantes = [c for c in clave if c not in self.nombres]

        if faltantes:
            raise ValueError(
                f"La clave de negocio usa columnas que no están en el esquema: {faltantes}"
            )

    # ---------------------------------------------------------------
    # Conversión de tipos
    # ---------------------------------------------------------------

    def convertir_tipos(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convierte las columnas a su tipo final para la carga en la base
        de datos. Se aplica a datos ya validados.
        """

        df = df.copy()

        for columna in self.columnas:
            if columna.nombre not in df.columns:
                continue

            serie = df[columna.nombre]

            if columna.tipo == "fecha":
                df[columna.nombre] = pd.to_datetime(serie).dt.date
            elif columna.tipo == "entero":
                df[columna.nombre] = pd.to_numeric(serie).astype("int64")
            elif columna.tipo == "decimal":
                df[columna.nombre] = pd.to_numeric(serie).astype("float64")
            elif columna.tipo == "booleano":
                df[columna.nombre] = serie.map(_a_booleano)
            else:
                df[columna.nombre] = serie.astype(str)

        return df


def _a_booleano(valor):
    if isinstance(valor, bool):
        return valor

    texto = str(valor).strip().lower()

    if texto in {"true", "1", "si", "sí", "s", "yes", "y", "verdadero"}:
        return True
    if texto in {"false", "0", "no", "n", "falso"}:
        return False

    raise ValueError(f"Valor booleano no reconocido: {valor!r}")


def construir_esquema(definicion: dict) -> Esquema:
    """Crea y valida un Esquema a partir de la sección 'esquema' de config.yaml."""

    if not isinstance(definicion, dict) or not definicion.get("columnas"):
        raise ValueError("La sección 'esquema' debe definir una lista 'columnas'.")

    columnas = []
    vistos = set()

    for indice, item in enumerate(definicion["columnas"], start=1):
        if not isinstance(item, dict) or "nombre" not in item or "tipo" not in item:
            raise ValueError(
                f"Columna #{indice} del esquema inválida: {item!r}. "
                "Cada columna requiere 'nombre' y 'tipo'."
            )

        desconocidas = set(item) - CLAVES_COLUMNA

        if desconocidas:
            raise ValueError(
                f"La columna '{item['nombre']}' tiene propiedades desconocidas: "
                f"{sorted(desconocidas)}. Permitidas: {sorted(CLAVES_COLUMNA)}"
            )

        validar_identificador(item["nombre"], "Nombre de columna del esquema")

        if item["tipo"] not in TIPOS_ADMITIDOS:
            raise ValueError(
                f"Tipo '{item['tipo']}' no admitido en la columna '{item['nombre']}'. "
                f"Tipos admitidos: {sorted(TIPOS_ADMITIDOS)}"
            )

        if item["nombre"] in vistos:
            raise ValueError(f"Columna duplicada en el esquema: {item['nombre']}")

        vistos.add(item["nombre"])
        columnas.append(Columna(**item))

    return Esquema(columnas=tuple(columnas))


def obtener_esquema(config: dict) -> Esquema:
    """Esquema del pipeline, validado contra la clave de negocio configurada."""

    if "esquema" not in config:
        raise ValueError("config.yaml no contiene la sección 'esquema'.")

    esquema = construir_esquema(config["esquema"])

    clave = config.get("pipeline", {}).get("clave_negocio")

    if clave:
        esquema.validar_clave(clave)

    return esquema
