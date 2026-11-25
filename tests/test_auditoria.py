
from unittest.mock import MagicMock

import pytest

from src import auditoria


@pytest.fixture
def conexion_simulada(monkeypatch):

    conexion = MagicMock()

    engine_simulado = MagicMock()

    engine_simulado.begin.return_value.__enter__.return_value = conexion

    monkeypatch.setattr(
        auditoria,
        "engine",
        engine_simulado
    )

    return engine_simulado, conexion


def test_registrar_inicio(conexion_simulada):

    engine, conexion = conexion_simulada

    conexion.execute.return_value.scalar_one.return_value = 25

    resultado = auditoria.registrar_inicio()

    assert resultado == 25

    engine.begin.assert_called_once()

    conexion.execute.assert_called_once()


def test_registrar_fin_exitoso(conexion_simulada):

    engine, conexion = conexion_simulada

    conexion.execute.return_value.rowcount = 1

    auditoria.registrar_fin(
        id_ejecucion=25,
        estado="EXITOSO",
        registros_extraidos=15,
        registros_limpios=12,
        registros_rechazados=3,
        operaciones_bd=0,
        duracion_segundos=7.25,
        mensaje_error=None
    )

    engine.begin.assert_called_once()

    conexion.execute.assert_called_once()


def test_registrar_fin_id_inexistente(conexion_simulada):

    engine, conexion = conexion_simulada

    conexion.execute.return_value.rowcount = 0

    with pytest.raises(
        ValueError,
        match="No se encontró la ejecución con ID 999"
    ):

        auditoria.registrar_fin(
            id_ejecucion=999,
            estado="EXITOSO"
        )

    engine.begin.assert_called_once()

    conexion.execute.assert_called_once()
