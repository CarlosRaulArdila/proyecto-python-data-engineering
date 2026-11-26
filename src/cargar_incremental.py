"""
Etapa 4 - Carga incremental (UPSERT) en PostgreSQL.

La consulta se genera a partir de la configuración:
- columnas a insertar:    las del `esquema`
- clave del ON CONFLICT:  `pipeline.clave_negocio`
- columnas a actualizar:  las demás (o `base_datos.columnas_actualizables`)
- columna de control:     `base_datos.columna_actualizacion` (opcional)

Solo se actualizan los registros cuyo contenido cambió (IS DISTINCT FROM),
por lo que una re-ejecución sin cambios realiza 0 operaciones (idempotencia).

Requiere un índice único sobre la clave de negocio en la tabla destino
(ver sql/migraciones/V001__crear_hospital_registros.sql).
"""

import logging
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from src.conexion_db import obtener_engine
from src.configuracion import CONFIG, resolver_ruta
from src.esquema import Esquema, obtener_esquema
from src.sql_utils import nombre_tabla, validar_identificador

logger = logging.getLogger(__name__)

# Obtener configuración desde config.yaml
PROCESSED_DIR = resolver_ruta(CONFIG["rutas"]["processed"])
RUTA_ARCHIVO = PROCESSED_DIR / CONFIG["archivos"]["validados"]

CONFIG_BD = CONFIG["base_datos"]

ESQUEMA_DESTINO = CONFIG_BD["esquema"]
TABLA_DESTINO = CONFIG_BD["tabla_destino"]
TABLA_CONFIGURADA = nombre_tabla(ESQUEMA_DESTINO, TABLA_DESTINO)


@dataclass(frozen=True)
class DefinicionUpsert:
    """Qué columnas se insertan, cuáles forman la clave y cuáles se actualizan."""

    columnas: tuple[str, ...]
    clave: tuple[str, ...]
    actualizables: tuple[str, ...]
    columna_actualizacion: str | None = None

    def __post_init__(self):
        for nombre in (*self.columnas, *self.clave, *self.actualizables):
            validar_identificador(nombre, "Nombre de columna")

        if self.columna_actualizacion:
            validar_identificador(self.columna_actualizacion, "Columna de actualización")

        if not self.clave:
            raise ValueError("La clave de negocio no puede estar vacía.")

        fuera = [c for c in (*self.clave, *self.actualizables) if c not in self.columnas]

        if fuera:
            raise ValueError(f"Columnas de clave o actualizables fuera del esquema: {fuera}")

        en_ambas = set(self.clave) & set(self.actualizables)

        if en_ambas:
            raise ValueError(
                f"Una columna no puede ser clave y actualizable a la vez: {sorted(en_ambas)}"
            )


def definicion_desde_config(
    config: dict = CONFIG, esquema: Esquema | None = None
) -> DefinicionUpsert:
    """Construye la definición del UPSERT a partir de config.yaml."""

    esquema = esquema or obtener_esquema(config)
    clave = tuple(config["pipeline"]["clave_negocio"])
    configuradas = config["base_datos"].get("columnas_actualizables")

    actualizables = (
        tuple(configuradas)
        if configuradas is not None
        else tuple(c for c in esquema.nombres if c not in clave)
    )

    return DefinicionUpsert(
        columnas=tuple(esquema.nombres),
        clave=clave,
        actualizables=actualizables,
        columna_actualizacion=config["base_datos"].get("columna_actualizacion"),
    )


def preparar_datos(ruta_archivo, esquema: Esquema | None = None):
    """
    Lee el archivo validado y convierte cada columna al tipo declarado
    en el esquema (fechas, enteros como 33.0 -> 33, etc.).
    """

    if not ruta_archivo.exists():
        raise FileNotFoundError(f"No se encontró el archivo validado: {ruta_archivo}")

    esquema = esquema or obtener_esquema(CONFIG)

    df = pd.read_csv(ruta_archivo, dtype=esquema.dtypes_lectura(), encoding="utf-8-sig")

    return esquema.convertir_tipos(df)


def construir_consulta(
    tabla, tablas_permitidas=None, definicion: DefinicionUpsert | None = None
) -> TextClause:
    """Genera el UPSERT para una tabla permitida."""

    tablas_permitidas = tablas_permitidas or {TABLA_CONFIGURADA}

    if tabla not in tablas_permitidas:
        raise ValueError(f"Tabla no permitida: {tabla}")

    esquema_bd, _, nombre = tabla.partition(".")
    tabla = nombre_tabla(esquema_bd, nombre)

    definicion = definicion or definicion_desde_config()

    columnas = ", ".join(definicion.columnas)
    valores = ", ".join(f":{c}" for c in definicion.columnas)
    clave = ", ".join(definicion.clave)

    if not definicion.actualizables:
        accion = "DO NOTHING"
    else:
        asignaciones = [f"{c} = EXCLUDED.{c}" for c in definicion.actualizables]

        if definicion.columna_actualizacion:
            asignaciones.append(f"{definicion.columna_actualizacion} = CURRENT_TIMESTAMP")

        cambios = "\n            OR ".join(
            f"destino.{c} IS DISTINCT FROM EXCLUDED.{c}" for c in definicion.actualizables
        )

        accion = (
            "DO UPDATE SET\n            "
            + ",\n            ".join(asignaciones)
            + "\n        WHERE\n            "
            + cambios
        )

    # Los identificadores están validados (sql_utils); los valores van como parámetros
    return text(
        f"INSERT INTO {tabla} AS destino ({columnas})\n"
        f"        VALUES ({valores})\n"
        f"        ON CONFLICT ({clave})\n"
        f"        {accion};"
    )


def verificar_tabla_destino(conexion, tabla: str, definicion: DefinicionUpsert) -> None:
    """Falla con un mensaje claro si la tabla no tiene las columnas esperadas."""

    esquema_bd, _, nombre = tabla.partition(".")

    existentes = set(
        conexion.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :esquema AND table_name = :tabla"
            ),
            {"esquema": esquema_bd, "tabla": nombre},
        ).scalars()
    )

    if not existentes:
        raise ValueError(
            f"La tabla destino {tabla} no existe. Ejecute: python -m src.migrar"
        )

    requeridas = set(definicion.columnas)

    if definicion.columna_actualizacion:
        requeridas.add(definicion.columna_actualizacion)

    faltantes = sorted(requeridas - existentes)

    if faltantes:
        raise ValueError(
            f"La tabla {tabla} no tiene las columnas {faltantes} definidas en "
            "config.yaml. Cree una migración que las agregue."
        )


def cargar_incremental(
    df,
    conexion,
    tabla=TABLA_CONFIGURADA,
    tablas_permitidas=None,
    definicion: DefinicionUpsert | None = None,
):
    """Ejecuta el UPSERT y devuelve el número de filas insertadas o actualizadas."""

    if df.empty:
        return 0

    definicion = definicion or definicion_desde_config()
    consulta = construir_consulta(tabla, tablas_permitidas, definicion)

    registros = df[list(definicion.columnas)].to_dict(orient="records")

    resultado = conexion.execute(consulta, registros)

    return resultado.rowcount


def ejecutar_carga_incremental() -> dict:
    """Ejecuta la etapa y devuelve sus métricas para la auditoría."""

    esquema = obtener_esquema(CONFIG)
    definicion = definicion_desde_config(CONFIG, esquema)
    df = preparar_datos(RUTA_ARCHIVO, esquema)

    with obtener_engine().begin() as conexion:
        verificar_tabla_destino(conexion, TABLA_CONFIGURADA, definicion)
        operaciones = cargar_incremental(df, conexion, definicion=definicion)

    logger.info(
        "Carga incremental finalizada | Registros procesados: %s | "
        "Operaciones (insertados o actualizados): %s | Tabla: %s | Clave: %s",
        len(df),
        operaciones,
        TABLA_CONFIGURADA,
        ", ".join(definicion.clave),
    )

    return {"operaciones_bd": operaciones}


if __name__ == "__main__":
    from src.registro_logs import configurar_logging

    configurar_logging()
    ejecutar_carga_incremental()
