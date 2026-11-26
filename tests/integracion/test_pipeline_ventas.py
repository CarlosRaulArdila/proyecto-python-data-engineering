"""
Prueba de fuego de la plantilla: el pipeline de ventas (pipelines/ventas)
funciona con el mismo motor, solo con configuración, en su propio esquema.

Requiere RUN_INTEGRATION_TESTS=1 y una base cuyo nombre termine en "_test".
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml
from sqlalchemy import create_engine, text

from src.conexion_db import construir_url

RAIZ = Path(__file__).resolve().parents[2]
PIPELINE = RAIZ / "pipelines" / "ventas"

pytestmark = [
    pytest.mark.integracion,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="Defina RUN_INTEGRATION_TESTS=1 para ejecutar las pruebas de integración",
    ),
]


@pytest.fixture(scope="module")
def engine():
    if not os.getenv("DB_NAME", "").endswith("_test"):
        pytest.fail("Por seguridad, DB_NAME debe terminar en '_test'.")

    motor = create_engine(construir_url())
    yield motor
    motor.dispose()


@pytest.fixture
def proyecto(tmp_path, engine):
    with engine.begin() as conexion:
        conexion.execute(text("DROP SCHEMA IF EXISTS ventas CASCADE"))

    config = yaml.safe_load((PIPELINE / "config.yaml").read_text(encoding="utf-8"))

    raw = tmp_path / "raw"
    raw.mkdir()

    config["rutas"] = {
        "raw": str(raw),
        "processed": str(tmp_path / "processed"),
        "rejected": str(tmp_path / "rejected"),
        "logs": str(tmp_path / "logs"),
    }

    ruta_config = tmp_path / "config.yaml"
    ruta_config.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    return {"ETL_CONFIG_PATH": str(ruta_config)}, raw, tmp_path


def ejecutar(modulo, entorno):
    resultado = subprocess.run(
        [sys.executable, "-m", modulo],
        cwd=RAIZ,
        env={**os.environ, **entorno},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    return resultado


def ultima_auditoria(engine):
    with engine.connect() as conexion:
        return tuple(conexion.execute(text(
            "SELECT estado, registros_extraidos, registros_limpios, registros_rechazados, "
            "operaciones_bd FROM ventas.etl_auditoria ORDER BY id DESC LIMIT 1"
        )).one())


def copiar(raw, *nombres):
    for nombre in nombres:
        shutil.copy(PIPELINE / "datos_ejemplo" / nombre, raw / nombre)


def test_pipeline_de_ventas_solo_con_configuracion(engine, proyecto):

    entorno, raw, tmp_path = proyecto

    migracion = ejecutar("src.migrar", entorno)
    assert "Creando el esquema ventas" in migracion.stdout
    assert "Migraciones aplicadas: [1, 2]" in migracion.stdout

    # Día 1: 10 registros, 1 incompleto, 1 duplicado, 4 fuera de reglas
    copiar(raw, "tienda_norte_2026-11-24.csv", "tienda_sur_2026-11-24.csv")
    ejecutar("src.ejecutar_pipeline", entorno)

    assert ultima_auditoria(engine) == ("EXITOSO", 10, 8, 6, 4)

    rechazados = pd.read_csv(tmp_path / "rejected" / "registros_fuera_reglas.csv", dtype=str)
    motivos = dict(zip(rechazados["pedido_id"], rechazados["errores_validacion"], strict=True))

    assert motivos == {
        "PED-000004": "Cantidad fuera del rango permitido (1 a 1000)",
        "PED-10003": "Pedido con formato inválido (esperado PED-000000)",
        "PED-100004": "Categoría no permitida",
        "PED-100005": "Canal de venta no permitido",
    }

    # Repetición sin archivos nuevos: no se procesa nada
    ejecutar("src.ejecutar_pipeline", entorno)
    assert ultima_auditoria(engine) == ("EXITOSO", 0, 0, 0, 0)

    # Día 2: un lote nuevo con un pedido nuevo y otro modificado
    copiar(raw, "tienda_norte_2026-11-25.csv")
    ejecutar("src.ejecutar_pipeline", entorno)
    assert ultima_auditoria(engine) == ("EXITOSO", 2, 2, 0, 2)

    with engine.connect() as conexion:
        pedidos = {
            fila.pedido_id: fila
            for fila in conexion.execute(text(
                "SELECT pedido_id, cantidad, precio_unitario, tienda_origen, "
                "fecha_actualizacion > fecha_creacion AS actualizado FROM ventas.pedidos"
            ))
        }
        archivos = conexion.execute(
            text("SELECT count(*) FROM ventas.etl_archivos_procesados")
        ).scalar()

    assert sorted(pedidos) == [
        "PED-000001", "PED-000002", "PED-000005", "PED-100001", "PED-100002"
    ]
    assert pedidos["PED-000001"].cantidad == 3
    assert pedidos["PED-000001"].actualizado
    assert float(pedidos["PED-000001"].precio_unitario) == 189900.0
    assert pedidos["PED-100001"].tienda_origen == "Tienda Sur"
    assert archivos == 3
