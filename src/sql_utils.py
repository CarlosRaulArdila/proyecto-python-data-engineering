"""
Utilidades para construir SQL de forma segura a partir de la configuración.

Los nombres de tablas y columnas no pueden pasarse como parámetros
(:valor) en SQL, así que se validan contra un patrón estricto antes de
insertarlos en la consulta. Solo se admiten identificadores simples en
minúsculas: letras, números y guion bajo, empezando por letra o guion bajo.
"""

import re

PATRON_IDENTIFICADOR = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def validar_identificador(nombre: str, contexto: str = "identificador") -> str:
    """Devuelve el nombre si es un identificador SQL seguro; si no, lanza ValueError."""

    if not isinstance(nombre, str) or not PATRON_IDENTIFICADOR.match(nombre):
        raise ValueError(
            f"{contexto} inválido: {nombre!r}. Use solo minúsculas, números y guion "
            "bajo, empezando por letra o guion bajo (máx. 63 caracteres)."
        )

    return nombre


def nombre_tabla(esquema: str, tabla: str) -> str:
    """Nombre calificado esquema.tabla, validado."""

    return (
        f"{validar_identificador(esquema, 'Esquema de base de datos')}."
        f"{validar_identificador(tabla, 'Nombre de tabla')}"
    )
