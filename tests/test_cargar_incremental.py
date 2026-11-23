
from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest

from src.cargar_incremental import (
    preparar_datos,
    construir_consulta,
    cargar_incremental
)


def test_preparar_datos(tmp_path):

    archivo = tmp_path / "datos.csv"

    df_original = pd.DataFrame({
        "numero_historia": ["001001"],
        "fecha": ["2026-01-10"],
        "edad": [45],
        "especialidad": ["Cirugia"],
        "tecnica_anestesica": ["General"],
        "duracion_minutos": [90],
        "hospital_origen": ["Hospital 1"]
    })

    df_original.to_csv(archivo, index=False)

    df = preparar_datos(archivo)

    assert len(df) == 1
    assert df.loc[0, "numero_historia"] == "001001"
    assert df.loc[0, "fecha"] == date(2026, 1, 10)


def test_construir_consulta_tabla_permitida():

    consulta = construir_consulta(
        "pruebas_etl.hospital_registros"
    )

    assert "INSERT INTO pruebas_etl.hospital_registros" in str(consulta)
    assert "ON CONFLICT" in str(consulta)
    assert "DO UPDATE SET" in str(consulta)


def test_rechazar_tabla_no_permitida():

    with pytest.raises(ValueError):
        construir_consulta("public.otra_tabla")


def test_cargar_incremental():

    df = pd.DataFrame([{
        "numero_historia": "001001",
        "fecha": date(2026, 1, 10),
        "edad": 45,
        "especialidad": "Cirugia",
        "tecnica_anestesica": "General",
        "duracion_minutos": 90,
        "hospital_origen": "Hospital 1"
    }])

    conexion = Mock()
    conexion.execute.return_value.rowcount = 1

    operaciones = cargar_incremental(
        df,
        conexion,
        "pruebas_etl.hospital_registros"
    )

    assert operaciones == 1
    conexion.execute.assert_called_once()
