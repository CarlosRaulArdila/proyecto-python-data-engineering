"""
Aplicador de migraciones SQL versionadas.

Ejecuta, en orden, los archivos V<NNN>__<descripcion>.sql del directorio
configurado (migraciones.directorio, por defecto sql/migraciones) que
todavía no se hayan aplicado, y registra cada uno en la tabla
<base_datos.esquema>.etl_migraciones (versión, nombre, checksum y fecha).

Cada proyecto tiene su propio esquema de PostgreSQL y su propio historial
de migraciones. Dentro de los archivos SQL pueden usarse los marcadores
{{esquema}} (base_datos.esquema) y {{zona_horaria}} (orquestacion.zona_horaria,
por defecto UTC); así una misma migración sirve para cualquier proyecto.

Características:
- Idempotente: volver a ejecutarlo no hace nada si no hay migraciones nuevas.
- Cada migración se aplica en su propia transacción.
- Bloqueo consultivo (advisory lock) para evitar ejecuciones simultáneas.
- Detecta si un archivo ya aplicado fue modificado (checksum distinto).
- Crea el esquema del proyecto si no existe.

Uso:
    python -m src.migrar
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from src.conexion_db import cerrar_engine, obtener_engine
from src.configuracion import CONFIG, resolver_ruta
from src.sql_utils import validar_identificador

logger = logging.getLogger(__name__)

DIRECTORIO_MIGRACIONES = resolver_ruta(
    CONFIG.get("migraciones", {}).get("directorio", "sql/migraciones")
)

ESQUEMA_BD = validar_identificador(CONFIG["base_datos"]["esquema"], "Esquema de base de datos")
TABLA_CONTROL = f"{ESQUEMA_BD}.etl_migraciones"

# Marcadores que se reemplazan dentro de los archivos SQL
ZONA_HORARIA = CONFIG.get("orquestacion", {}).get("zona_horaria", "UTC")

if not re.fullmatch(r"[A-Za-z_]+(/[A-Za-z0-9_\-+]+)*", ZONA_HORARIA):
    raise ValueError(f"orquestacion.zona_horaria inválida: {ZONA_HORARIA!r}")

MARCADORES = {
    "{{esquema}}": ESQUEMA_BD,
    "{{zona_horaria}}": ZONA_HORARIA,
}

PATRON_ARCHIVO = re.compile(r"^V(\d+)__([\w\-]+)\.sql$")

# Identificador arbitrario del bloqueo consultivo de migraciones
ID_BLOQUEO = 7_301_202_601

SQL_TABLA_CONTROL = f"""
CREATE TABLE IF NOT EXISTS {TABLA_CONTROL} (
    version           INTEGER      PRIMARY KEY,
    nombre            VARCHAR(200) NOT NULL,
    checksum          CHAR(64)     NOT NULL,
    fecha_aplicacion  TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@dataclass(frozen=True)
class Migracion:
    version: int
    nombre: str
    ruta: Path

    @property
    def sql(self) -> str:
        contenido = self.ruta.read_text(encoding="utf-8")

        for marcador, valor in MARCADORES.items():
            contenido = contenido.replace(marcador, valor)

        return contenido

    @property
    def checksum(self) -> str:
        # Se normalizan los finales de línea: el mismo archivo con CRLF
        # (Windows) o LF (Linux/CI) debe tener el mismo checksum.
        contenido = self.ruta.read_bytes().replace(b"\r\n", b"\n")
        return hashlib.sha256(contenido).hexdigest()


def listar_migraciones(directorio: Path | None = None) -> list[Migracion]:
    """Devuelve las migraciones del directorio ordenadas por versión."""

    directorio = directorio or DIRECTORIO_MIGRACIONES

    if not directorio.is_dir():
        raise FileNotFoundError(f"No existe el directorio de migraciones: {directorio}")

    migraciones = []

    for ruta in directorio.glob("*.sql"):
        coincidencia = PATRON_ARCHIVO.match(ruta.name)

        if not coincidencia:
            raise ValueError(
                f"Nombre de migración inválido: {ruta.name}. "
                "Formato esperado: V<numero>__<descripcion>.sql"
            )

        migraciones.append(
            Migracion(
                version=int(coincidencia.group(1)),
                nombre=coincidencia.group(2),
                ruta=ruta,
            )
        )

    migraciones.sort(key=lambda m: m.version)

    versiones = [m.version for m in migraciones]
    duplicadas = {v for v in versiones if versiones.count(v) > 1}

    if duplicadas:
        raise ValueError(f"Versiones de migración duplicadas: {sorted(duplicadas)}")

    return migraciones


def aplicar_migraciones(directorio: Path | None = None) -> list[int]:
    """Aplica las migraciones pendientes. Devuelve las versiones aplicadas."""

    directorio = directorio or DIRECTORIO_MIGRACIONES
    migraciones = listar_migraciones(directorio)
    engine = obtener_engine()
    aplicadas_ahora = []

    with engine.connect() as conexion:
        # SQLAlchemy 2.0 inicia transacciones implícitas: se confirma
        # explícitamente cada paso para poder abrir bloques begin() propios.
        conexion.execute(text("SELECT pg_advisory_lock(:id)"), {"id": ID_BLOQUEO})
        conexion.commit()

        try:
            # Solo se intenta crear la tabla de control si no existe: así un
            # usuario de servicio sin permisos de DDL puede ejecutar este paso
            # cuando no hay migraciones pendientes (por ejemplo, desde Airflow).
            with conexion.begin():
                existe_esquema = conexion.execute(
                    text("SELECT to_regnamespace(:esquema) IS NOT NULL"),
                    {"esquema": ESQUEMA_BD},
                ).scalar()

                if not existe_esquema:
                    logger.info("Creando el esquema %s", ESQUEMA_BD)
                    conexion.execute(text(f"CREATE SCHEMA {ESQUEMA_BD}"))

                existe_control = conexion.execute(
                    text("SELECT to_regclass(:tabla) IS NOT NULL"),
                    {"tabla": TABLA_CONTROL},
                ).scalar()

                if not existe_control:
                    conexion.execute(text(SQL_TABLA_CONTROL))

            with conexion.begin():
                registradas = {
                    fila.version: fila.checksum
                    for fila in conexion.execute(
                        text(f"SELECT version, checksum FROM {TABLA_CONTROL}")
                    )
                }

            for migracion in migraciones:
                if migracion.version in registradas:
                    if registradas[migracion.version] != migracion.checksum:
                        raise RuntimeError(
                            f"La migración V{migracion.version:03d} "
                            f"({migracion.ruta.name}) fue modificada después de "
                            "aplicarse. Cree una nueva migración en lugar de "
                            "editar una existente."
                        )
                    continue

                logger.info("Aplicando migración %s", migracion.ruta.name)

                with conexion.begin():
                    # exec_driver_sql permite varios comandos y bloques DO $$...$$
                    conexion.exec_driver_sql(migracion.sql)
                    conexion.execute(
                        text(
                            f"INSERT INTO {TABLA_CONTROL} "
                            "(version, nombre, checksum) "
                            "VALUES (:version, :nombre, :checksum)"
                        ),
                        {
                            "version": migracion.version,
                            "nombre": migracion.nombre,
                            "checksum": migracion.checksum,
                        },
                    )

                aplicadas_ahora.append(migracion.version)

        finally:
            conexion.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": ID_BLOQUEO})
            conexion.commit()

    logger.info("Directorio: %s | Control: %s", directorio, TABLA_CONTROL)

    if aplicadas_ahora:
        logger.info("Migraciones aplicadas: %s", aplicadas_ahora)
    else:
        logger.info("La base de datos ya está actualizada. No hay migraciones pendientes.")

    return aplicadas_ahora


def main() -> int:
    from src.registro_logs import configurar_logging

    configurar_logging()

    try:
        aplicar_migraciones()
        return 0
    except Exception:
        logger.exception("Error al aplicar las migraciones")
        return 1
    finally:
        cerrar_engine()


if __name__ == "__main__":
    raise SystemExit(main())
