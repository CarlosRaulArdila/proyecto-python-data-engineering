
import importlib

import pytest

from src import conexion_db

VARIABLES = {
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "base_prueba",
    "DB_USER": "usuario",
    "DB_PASSWORD": "clave",
}


@pytest.fixture(autouse=True)
def engine_limpio():
    conexion_db.cerrar_engine()
    yield
    conexion_db.cerrar_engine()


def test_importar_modulo_no_exige_credenciales(monkeypatch):
    for nombre in VARIABLES:
        monkeypatch.delenv(nombre, raising=False)

    # No debe lanzar excepción al importarse sin .env
    importlib.reload(conexion_db)


def test_obtener_engine_sin_variables_indica_cuales_faltan(monkeypatch):
    for nombre in VARIABLES:
        monkeypatch.delenv(nombre, raising=False)

    with pytest.raises(ValueError, match="DB_HOST.*DB_PASSWORD"):
        conexion_db.obtener_engine()


def test_obtener_engine_reutiliza_la_instancia(monkeypatch):
    for nombre, valor in VARIABLES.items():
        monkeypatch.setenv(nombre, valor)

    primero = conexion_db.obtener_engine()
    segundo = conexion_db.obtener_engine()

    assert primero is segundo
    assert primero.url.database == "base_prueba"
    assert primero.url.port == 5432


def test_cerrar_engine_permite_crear_uno_nuevo(monkeypatch):
    for nombre, valor in VARIABLES.items():
        monkeypatch.setenv(nombre, valor)

    primero = conexion_db.obtener_engine()
    conexion_db.cerrar_engine()
    segundo = conexion_db.obtener_engine()

    assert primero is not segundo
