"""
Motor de reglas de validación declaradas en config.yaml.

Hay dos fuentes de reglas:

1. Automáticas, derivadas del esquema (src/esquema.py):
   - obligatoria:   el valor no puede estar vacío
   - tipo:          fecha válida, número entero o decimal, booleano
   - longitud_max:  longitud máxima de los textos

2. De negocio, declaradas en la sección `reglas` de config.yaml:

    reglas:
      - columna: "edad"
        tipo: "rango"
        min: 0
        max: 120
        mensaje: "Edad fuera del rango permitido"

      - columna: "duracion_minutos"
        tipo: "rango"
        min: 0
        min_inclusivo: false          # estrictamente mayor que 0
        mensaje: "Duración inválida"

      - columna: "especialidad"
        tipo: "valores_permitidos"
        valores: ["Cirugia", "Urologia"]
        mensaje: "Especialidad no permitida"

      - columna: "codigo"
        tipo: "patron"
        patron: "^[A-Z]{3}-\\d{4}$"
        mensaje: "Código con formato inválido"

La validación es vectorizada (sin recorrer filas una a una). Cada
registro rechazado indica todos sus motivos en `errores_validacion`.

Para añadir un tipo de regla nuevo: escribir una función
(serie, regla) -> máscara de filas que FALLAN, y registrarla en
TIPOS_REGLA con sus parámetros obligatorios.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from src.esquema import Esquema

COLUMNA_ERRORES = "errores_validacion"
SEPARADOR_ERRORES = "; "


@dataclass(frozen=True)
class Regla:
    columna: str
    tipo: str
    mensaje: str
    parametros: dict = field(default_factory=dict)


# ------------------------------------------------------------------
# Tipos de regla de negocio
# Cada función recibe la serie (ya convertida al tipo del esquema,
# con NaN donde no se pudo convertir) y devuelve True donde FALLA.
# Los valores nulos no se evalúan aquí: los cubre la regla obligatoria.
# ------------------------------------------------------------------


def _falla_rango(serie: pd.Series, regla: Regla) -> pd.Series:
    p = regla.parametros
    falla = pd.Series(False, index=serie.index)

    if "min" in p:
        limite = p["min"]
        falla |= serie < limite if p.get("min_inclusivo", True) else serie <= limite

    if "max" in p:
        limite = p["max"]
        falla |= serie > limite if p.get("max_inclusivo", True) else serie >= limite

    return falla & serie.notna()


def _falla_valores_permitidos(serie: pd.Series, regla: Regla) -> pd.Series:
    permitidos = set(regla.parametros["valores"])
    return ~serie.isin(permitidos) & serie.notna()


def _falla_patron(serie: pd.Series, regla: Regla) -> pd.Series:
    patron = re.compile(regla.parametros["patron"])
    cumple = serie.map(lambda valor: pd.isna(valor) or bool(patron.fullmatch(str(valor))))
    return ~cumple.astype(bool) & serie.notna()


TIPOS_REGLA: dict[str, tuple[Callable, set, set]] = {
    # tipo: (función, parámetros obligatorios, parámetros opcionales)
    "rango": (_falla_rango, set(), {"min", "max", "min_inclusivo", "max_inclusivo"}),
    "valores_permitidos": (_falla_valores_permitidos, {"valores"}, set()),
    "patron": (_falla_patron, {"patron"}, set()),
}


# ------------------------------------------------------------------
# Construcción y validación de la configuración
# ------------------------------------------------------------------


def construir_reglas(definiciones: list | None, esquema: Esquema) -> list[Regla]:
    """Crea las reglas de negocio y comprueba que sean coherentes con el esquema."""

    reglas = []

    for indice, item in enumerate(definiciones or [], start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Regla #{indice} inválida: {item!r}")

        faltantes = [c for c in ("columna", "tipo", "mensaje") if c not in item]

        if faltantes:
            raise ValueError(f"A la regla #{indice} ({item!r}) le faltan: {faltantes}")

        columna, tipo = item["columna"], item["tipo"]

        if columna not in esquema.nombres:
            raise ValueError(
                f"La regla #{indice} usa la columna '{columna}', que no está en el esquema."
            )

        if tipo not in TIPOS_REGLA:
            raise ValueError(
                f"Tipo de regla '{tipo}' no admitido (regla #{indice}). "
                f"Tipos admitidos: {sorted(TIPOS_REGLA)}"
            )

        _, obligatorios, opcionales = TIPOS_REGLA[tipo]
        parametros = {k: v for k, v in item.items() if k not in ("columna", "tipo", "mensaje")}

        sin_definir = obligatorios - set(parametros)
        desconocidos = set(parametros) - obligatorios - opcionales

        if sin_definir:
            raise ValueError(f"La regla #{indice} ({tipo}) requiere: {sorted(sin_definir)}")

        if desconocidos:
            raise ValueError(
                f"La regla #{indice} ({tipo}) tiene parámetros desconocidos: "
                f"{sorted(desconocidos)}"
            )

        if tipo == "rango" and not ({"min", "max"} & set(parametros)):
            raise ValueError(f"La regla #{indice} (rango) requiere 'min', 'max' o ambos.")

        if tipo == "rango" and esquema.columna(columna).tipo not in ("entero", "decimal"):
            raise ValueError(
                f"La regla #{indice} (rango) solo aplica a columnas numéricas; "
                f"'{columna}' es de tipo {esquema.columna(columna).tipo}."
            )

        if tipo == "patron":
            try:
                re.compile(parametros["patron"])
            except re.error as error:
                raise ValueError(f"Patrón inválido en la regla #{indice}: {error}") from error

        reglas.append(
            Regla(columna=columna, tipo=tipo, mensaje=item["mensaje"], parametros=parametros)
        )

    return reglas


# ------------------------------------------------------------------
# Validación
# ------------------------------------------------------------------


def _es_vacio(serie: pd.Series) -> pd.Series:
    vacio = serie.isna()

    if pd.api.types.is_object_dtype(serie) or pd.api.types.is_string_dtype(serie):
        vacio |= serie.astype(str).str.strip().eq("")

    return vacio


def validar_dataframe(df: pd.DataFrame, esquema: Esquema, reglas: list[Regla]):
    """
    Aplica las reglas automáticas del esquema y las reglas de negocio.

    Devuelve (df_validos, df_rechazados). Los rechazados incluyen la
    columna errores_validacion con todos los motivos separados por "; ".
    """

    errores: dict = {indice: [] for indice in df.index}

    def registrar(mascara: pd.Series, mensaje: str) -> None:
        for indice in mascara[mascara].index:
            errores[indice].append(mensaje)

    convertidas: dict[str, pd.Series] = {}

    # 1. Reglas automáticas del esquema
    for columna in esquema.columnas:
        if columna.nombre not in df.columns:
            continue

        etiqueta = columna.etiqueta or columna.nombre
        serie = df[columna.nombre]
        vacio = _es_vacio(serie)

        if columna.obligatoria:
            registrar(vacio, f"{etiqueta} vacío")

        if columna.tipo == "fecha":
            convertida = pd.to_datetime(serie, errors="coerce")
            registrar(convertida.isna() & ~vacio, f"{etiqueta} inválida")

        elif columna.tipo in ("entero", "decimal"):
            convertida = pd.to_numeric(serie, errors="coerce")
            registrar(convertida.isna() & ~vacio, f"{etiqueta} no es un número")

            if columna.tipo == "entero":
                no_entero = convertida.notna() & (convertida % 1 != 0)
                registrar(no_entero, f"{etiqueta} no es un número entero")

        else:
            convertida = serie.where(~vacio)

            if columna.longitud_max:
                largo = convertida.astype(str).str.len()
                registrar(
                    convertida.notna() & (largo > columna.longitud_max),
                    f"{etiqueta} supera {columna.longitud_max} caracteres",
                )

        convertidas[columna.nombre] = convertida

    # 2. Reglas de negocio
    for regla in reglas:
        if regla.columna not in convertidas:
            continue

        funcion, _, _ = TIPOS_REGLA[regla.tipo]
        registrar(funcion(convertidas[regla.columna], regla), regla.mensaje)

    resultado = df.copy()
    resultado[COLUMNA_ERRORES] = pd.Series(
        {indice: SEPARADOR_ERRORES.join(mensajes) for indice, mensajes in errores.items()},
        dtype=object,
    )

    mascara_validos = resultado[COLUMNA_ERRORES] == ""

    df_validos = resultado.loc[mascara_validos].drop(columns=[COLUMNA_ERRORES])
    df_rechazados = resultado.loc[~mascara_validos].copy()

    return df_validos, df_rechazados
