"""
Pruebas de integración end-to-end contra un PostgreSQL real.

Se ejecutan solo con RUN_INTEGRATION_TESTS=1 y DB_* apuntando a una
base de datos DESECHABLE cuyo nombre termine en "_test": las pruebas
eliminan y recrean las tablas del proyecto.

    RUN_INTEGRATION_TESTS=1 DB_NAME=hospital_dw_test ... pytest -m integracion
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from sqlalchemy import create_engine, text

from src.conexion_db import construir_url

RAIZ = Path(__file__).resolve().parents[2]

pytestmark = [
    pytest.mark.integracion,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="Defina RUN_INTEGRATION_TESTS=1 para ejecutar las pruebas de integración",
    ),
]

DDL_VERSION_ANTERIOR = """
CREATE TABLE hospital_registros (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_historia VARCHAR(20) NOT NULL,
    fecha DATE NOT NULL,
    edad INTEGER NOT NULL,
    especialidad VARCHAR(50) NOT NULL,
    tecnica_anestesica VARCHAR(50) NOT NULL,
    duracion_minutos INTEGER NOT NULL,
    hospital_origen VARCHAR(100) NOT NULL
);
"""


@pytest.fixture(scope="module")
def engine():
    if not os.getenv("DB_NAME", "").endswith("_test"):
        pytest.fail(
            "Por seguridad, DB_NAME debe terminar en '_test' "
            "(las pruebas eliminan tablas)."
        )

    motor = create_engine(construir_url())
    yield motor
    motor.dispose()


def reiniciar_base(engine):
    with engine.begin() as conexion:
        conexion.execute(text(
            "DROP TABLE IF EXISTS public.hospital_registros, "
            "public.etl_auditoria, public.etl_migraciones"
        ))


def ejecutar(modulo, entorno_extra=None):
    entorno = {**os.environ, **(entorno_extra or {})}

    return subprocess.run(
        [sys.executable, "-m", modulo],
        cwd=RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture
def proyecto_temporal(tmp_path):
    """Config apuntando a carpetas temporales con los CSV de ejemplo."""

    config = yaml.safe_load((RAIZ / "config" / "config.yaml").read_text(encoding="utf-8"))

    raw = tmp_path / "raw"
    raw.mkdir()

    for fuente in config["fuentes"]:
        shutil.copy(RAIZ / "tests" / "datos" / fuente["archivo"], raw / fuente["archivo"])

    config["rutas"] = {
        "raw": str(raw),
        "processed": str(tmp_path / "processed"),
        "rejected": str(tmp_path / "rejected"),
        "logs": str(tmp_path / "logs"),
    }

    ruta_config = tmp_path / "config.yaml"
    ruta_config.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    return {"ETL_CONFIG_PATH": str(ruta_config)}, raw


def test_migraciones_actualizan_una_base_de_la_version_anterior(engine):

    reiniciar_base(engine)

    with engine.begin() as conexion:
        conexion.execute(text(DDL_VERSION_ANTERIOR))
        conexion.execute(text(
            "INSERT INTO hospital_registros (numero_historia, fecha, edad, especialidad, "
            "tecnica_anestesica, duracion_minutos, hospital_origen) "
            "VALUES ('999', '2026-01-01', 50, 'Cirugia', 'General', 60, 'Hospital 1')"
        ))

    primera = ejecutar("src.migrar")
    assert primera.returncode == 0, primera.stdout + primera.stderr

    segunda = ejecutar("src.migrar")
    assert segunda.returncode == 0, segunda.stdout + segunda.stderr
    assert "No hay migraciones pendientes" in segunda.stdout

    with engine.connect() as conexion:
        versiones = conexion.execute(
            text("SELECT version FROM etl_migraciones ORDER BY version")
        ).scalars().all()
        filas = conexion.execute(text("SELECT count(*) FROM hospital_registros")).scalar()
        columnas = set(conexion.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'hospital_registros'"
        )).scalars())

    assert versiones == [1, 2, 3]
    assert filas == 1
    assert {"fecha_creacion", "fecha_actualizacion"} <= columnas


def test_pipeline_completo_idempotente_e_incremental(engine, proyecto_temporal):

    entorno, raw = proyecto_temporal

    reiniciar_base(engine)
    assert ejecutar("src.migrar").returncode == 0

    # 1. Primera carga: 15 extraídos, 12 limpios, 3 rechazados, 12 insertados
    resultado = ejecutar("src.ejecutar_pipeline", entorno)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    with engine.connect() as conexion:
        assert conexion.execute(text("SELECT count(*) FROM hospital_registros")).scalar() == 12
        auditoria = conexion.execute(text(
            "SELECT estado, registros_extraidos, registros_limpios, "
            "registros_rechazados, operaciones_bd "
            "FROM etl_auditoria ORDER BY id DESC LIMIT 1"
        )).one()

    assert tuple(auditoria) == ("EXITOSO", 15, 12, 3, 12)

    # 2. Re-ejecución sin cambios: 0 operaciones (idempotencia)
    resultado = ejecutar("src.ejecutar_pipeline", entorno)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    with engine.connect() as conexion:
        operaciones = conexion.execute(text(
            "SELECT operaciones_bd FROM etl_auditoria ORDER BY id DESC LIMIT 1"
        )).scalar()

    assert operaciones == 0

    # 3. Un registro modificado en la fuente: 1 operación (actualización)
    archivo = raw / "hospital_1.csv"
    contenido = archivo.read_text(encoding="utf-8-sig")
    archivo.write_text(
        contenido.replace("001001,2026-01-10,45,", "001001,2026-01-10,46,"),
        encoding="utf-8-sig",
    )

    resultado = ejecutar("src.ejecutar_pipeline", entorno)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    with engine.connect() as conexion:
        operaciones = conexion.execute(text(
            "SELECT operaciones_bd FROM etl_auditoria ORDER BY id DESC LIMIT 1"
        )).scalar()
        edad = conexion.execute(text(
            "SELECT edad FROM hospital_registros WHERE numero_historia = '001001'"
        )).scalar()

    assert operaciones == 1
    assert edad == 46


def test_fallo_de_fuente_queda_auditado(engine, proyecto_temporal):

    entorno, raw = proyecto_temporal

    reiniciar_base(engine)
    assert ejecutar("src.migrar").returncode == 0

    (raw / "hospital_2.csv").unlink()

    resultado = ejecutar("src.ejecutar_pipeline", entorno)
    assert resultado.returncode == 1

    with engine.connect() as conexion:
        estado, mensaje = conexion.execute(text(
            "SELECT estado, mensaje_error FROM etl_auditoria ORDER BY id DESC LIMIT 1"
        )).one()

    assert estado == "FALLIDO"
    assert "hospital_2.csv" in mensaje
