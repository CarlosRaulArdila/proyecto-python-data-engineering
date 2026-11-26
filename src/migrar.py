"""
Aplicador de migraciones SQL versionadas.

Ejecuta, en orden, los archivos sql/migraciones/V<NNN>__<descripcion>.sql
que todavía no se hayan aplicado, y registra cada uno en la tabla
public.etl_migraciones (versión, nombre, checksum y fecha).

Características:
- Idempotente: volver a ejecutarlo no hace nada si no hay migraciones nuevas.
- Cada migración se aplica en su propia transacción.
- Bloqueo consultivo (advisory lock) para evitar ejecuciones simultáneas.
- Detecta si un archivo ya aplicado fue modificado (checksum distinto).

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
from src.configuracion import BASE_DIR

logger = logging.getLogger(__name__)

DIRECTORIO_MIGRACIONES = BASE_DIR / "sql" / "migraciones"

PATRON_ARCHIVO = re.compile(r"^V(\d+)__([\w\-]+)\.sql$")

# Identificador arbitrario del bloqueo consultivo de migraciones
ID_BLOQUEO = 7_301_202_601

SQL_TABLA_CONTROL = """
CREATE TABLE IF NOT EXISTS public.etl_migraciones (
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
        return self.ruta.read_text(encoding="utf-8")

    @property
    def checksum(self) -> str:
        # Se normalizan los finales de línea: el mismo archivo con CRLF
        # (Windows) o LF (Linux/CI) debe tener el mismo checksum.
        contenido = self.ruta.read_bytes().replace(b"\r\n", b"\n")
        return hashlib.sha256(contenido).hexdigest()


def listar_migraciones(directorio: Path = DIRECTORIO_MIGRACIONES) -> list[Migracion]:
    """Devuelve las migraciones del directorio ordenadas por versión."""

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


def aplicar_migraciones(directorio: Path = DIRECTORIO_MIGRACIONES) -> list[int]:
    """Aplica las migraciones pendientes. Devuelve las versiones aplicadas."""

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
                existe_control = conexion.execute(
                    text("SELECT to_regclass('public.etl_migraciones') IS NOT NULL")
                ).scalar()

                if not existe_control:
                    conexion.execute(text(SQL_TABLA_CONTROL))

            with conexion.begin():
                registradas = {
                    fila.version: fila.checksum
                    for fila in conexion.execute(
                        text("SELECT version, checksum FROM public.etl_migraciones")
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
                            "INSERT INTO public.etl_migraciones "
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
