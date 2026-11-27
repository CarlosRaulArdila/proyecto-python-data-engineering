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
            "public.etl_auditoria, public.etl_migraciones, public.etl_archivos_procesados, "
            "public.etl_rechazos"
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

    return crear_proyecto(tmp_path)


def crear_proyecto(tmp_path, ajustar=None):
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

    if ajustar:
        ajustar(config)

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

    assert versiones == [1, 2, 3, 4, 5, 6]
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


def consultar(engine, sql):
    with engine.connect() as conexion:
        return conexion.execute(text(sql)).all()


def test_linaje_registra_los_archivos_de_cada_ejecucion(engine, proyecto_temporal):

    entorno, _ = proyecto_temporal

    reiniciar_base(engine)
    assert ejecutar("src.migrar").returncode == 0

    resultado = ejecutar("src.ejecutar_pipeline", entorno)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    filas = consultar(engine, """
        SELECT a.nombre_archivo, a.fuente, a.registros, length(a.hash_sha256)
        FROM etl_archivos_procesados a
        JOIN etl_auditoria e ON e.run_id = a.run_id
        ORDER BY a.nombre_archivo
    """)

    assert [tuple(f) for f in filas] == [
        ("hospital_1.csv", "Hospital 1", 5, 64),
        ("hospital_2.csv", "Hospital 2", 5, 64),
        ("hospital_3.csv", "Hospital 3", 5, 64),
    ]


def test_ingesta_incremental_por_lotes(engine, tmp_path):

    def modo_incremental_con_patrones(config):
        config["ingesta"] = {"modo": "incremental"}
        # Los lotes de esta prueba son pequeños: sin mínimo de registros
        config["calidad"] = {"max_porcentaje_rechazo": 30, "accion": "fallar"}
        config["fuentes"] = [
            {"nombre": "Hospital 1", "patron": "hospital_1*.csv"},
            {"nombre": "Hospital 2", "patron": "hospital_2*.csv"},
            {"nombre": "Hospital 3", "patron": "hospital_3*.csv"},
        ]

    entorno, raw = crear_proyecto(tmp_path, modo_incremental_con_patrones)

    reiniciar_base(engine)
    assert ejecutar("src.migrar").returncode == 0

    def ultima_auditoria():
        return tuple(consultar(engine, """
            SELECT estado, registros_extraidos, operaciones_bd
            FROM etl_auditoria ORDER BY id DESC LIMIT 1
        """)[0])

    # 1. Primera ejecución: carga los 3 archivos
    assert ejecutar("src.ejecutar_pipeline", entorno).returncode == 0
    assert ultima_auditoria() == ("EXITOSO", 15, 12)

    # 2. Sin archivos nuevos: termina bien sin leer nada
    resultado = ejecutar("src.ejecutar_pipeline", entorno)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "Omitido (ya procesado): hospital_1.csv" in resultado.stdout
    assert ultima_auditoria() == ("EXITOSO", 0, 0)

    # 3. Llega un lote nuevo de Hospital 1: solo se procesa ese archivo
    (raw / "hospital_1_lote_2.csv").write_text(
        "numero_historia,fecha,edad,especialidad,tecnica_anestesica,duracion_minutos\n"
        "001006,2026-02-01,50,Cirugia,General,95\n"
        "001007,2026-02-02,61,Urologia,Regional,70\n",
        encoding="utf-8",
    )

    resultado = ejecutar("src.ejecutar_pipeline", entorno)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert ultima_auditoria() == ("EXITOSO", 2, 2)

    # 4. El mismo contenido con otro nombre también se omite (hash)
    (raw / "hospital_1_lote_2_copia.csv").write_bytes(
        (raw / "hospital_1_lote_2.csv").read_bytes()
    )

    assert ejecutar("src.ejecutar_pipeline", entorno).returncode == 0
    assert ultima_auditoria() == ("EXITOSO", 0, 0)

    total = consultar(engine, "SELECT count(*) FROM hospital_registros")[0][0]
    archivos = consultar(engine, "SELECT count(*) FROM etl_archivos_procesados")[0][0]

    assert total == 14
    assert archivos == 4


def test_si_la_carga_falla_los_archivos_no_se_registran(engine, tmp_path):

    def incremental(config):
        config["ingesta"] = {"modo": "incremental"}

    entorno, _ = crear_proyecto(tmp_path, incremental)

    reiniciar_base(engine)
    assert ejecutar("src.migrar").returncode == 0

    # Se rompe la tabla destino: la carga fallará
    with engine.begin() as conexion:
        conexion.execute(text("ALTER TABLE hospital_registros RENAME COLUMN edad TO edad_x"))

    resultado = ejecutar("src.ejecutar_pipeline", entorno)
    assert resultado.returncode == 1
    assert "no tiene las columnas ['edad']" in resultado.stdout

    archivos = consultar(engine, "SELECT count(*) FROM etl_archivos_procesados")[0][0]
    assert archivos == 0

    # Corregida la tabla, la siguiente ejecución vuelve a procesar los archivos
    with engine.begin() as conexion:
        conexion.execute(text("ALTER TABLE hospital_registros RENAME COLUMN edad_x TO edad"))

    assert ejecutar("src.ejecutar_pipeline", entorno).returncode == 0

    assert consultar(engine, "SELECT count(*) FROM etl_archivos_procesados")[0][0] == 3
    assert consultar(engine, "SELECT count(*) FROM hospital_registros")[0][0] == 12


def test_umbral_de_calidad_detiene_la_carga(engine, tmp_path):

    def umbral_estricto(config):
        config["ingesta"] = {"modo": "incremental"}
        config["calidad"] = {"max_porcentaje_rechazo": 10, "accion": "fallar"}

    entorno, _ = crear_proyecto(tmp_path, umbral_estricto)

    reiniciar_base(engine)
    assert ejecutar("src.migrar").returncode == 0

    # 3 de 15 rechazados = 20 % > 10 %: no debe cargarse nada
    resultado = ejecutar("src.ejecutar_pipeline", entorno)
    assert resultado.returncode == 1

    estado, mensaje = consultar(
        engine, "SELECT estado, mensaje_error FROM etl_auditoria ORDER BY id DESC LIMIT 1"
    )[0]

    assert estado == "FALLIDO"
    assert "20.0 %" in mensaje and "máximo permitido es 10 %" in mensaje
    assert consultar(engine, "SELECT count(*) FROM hospital_registros")[0][0] == 0

    # Los rechazos que provocaron el fallo quedan guardados para investigarlos
    assert consultar(engine, "SELECT count(*) FROM etl_rechazos")[0][0] == 3
    assert consultar(engine, "SELECT count(*) FROM etl_archivos_procesados")[0][0] == 0


def test_umbral_en_modo_advertir_carga_y_anota(engine, tmp_path):

    def solo_advertir(config):
        config["calidad"] = {"max_porcentaje_rechazo": 10, "accion": "advertir"}

    entorno, _ = crear_proyecto(tmp_path, solo_advertir)

    reiniciar_base(engine)
    assert ejecutar("src.migrar").returncode == 0

    resultado = ejecutar("src.ejecutar_pipeline", entorno)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    estado, advertencias = consultar(
        engine, "SELECT estado, advertencias FROM etl_auditoria ORDER BY id DESC LIMIT 1"
    )[0]

    assert estado == "EXITOSO"
    assert "Se rechazó el 20.0 %" in advertencias
    assert consultar(engine, "SELECT count(*) FROM hospital_registros")[0][0] == 12


def test_historial_de_rechazos(engine, proyecto_temporal):

    entorno, _ = proyecto_temporal

    reiniciar_base(engine)
    assert ejecutar("src.migrar").returncode == 0

    for _ in range(2):
        resultado = ejecutar("src.ejecutar_pipeline", entorno)
        assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    filas = consultar(engine, """
        SELECT r.tipo, r.motivo, r.fuente, r.registro->>'numero_historia'
        FROM etl_rechazos r
        WHERE r.run_id = (SELECT run_id FROM etl_auditoria ORDER BY id DESC LIMIT 1)
        ORDER BY 4
    """)

    assert [tuple(f) for f in filas] == [
        ("incompleto", "Campos obligatorios vacíos: edad", "Hospital 2", "002003"),
        ("incompleto", "Campos obligatorios vacíos: tecnica_anestesica", "Hospital 2", "002004"),
        ("duplicado", "Registro duplicado exacto", "Hospital 3", "003004"),
    ]

    # Cada ejecución conserva su propio historial (no se sobrescribe)
    por_ejecucion = consultar(
        engine, "SELECT run_id, count(*) FROM etl_rechazos GROUP BY run_id"
    )
    assert len(por_ejecucion) == 2
    assert all(cantidad == 3 for _, cantidad in por_ejecucion)

    # El registro original completo se conserva (el vacío queda como null)
    registro = consultar(
        engine,
        "SELECT registro FROM etl_rechazos WHERE registro->>'numero_historia' = '002003' LIMIT 1",
    )[0][0]

    assert registro["edad"] is None
    assert registro["especialidad"] == "Traumatologia"
