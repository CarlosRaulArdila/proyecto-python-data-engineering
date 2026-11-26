
from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest

from src.cargar_incremental import (
    cargar_incremental,
    construir_consulta,
    preparar_datos,
)

TABLA_PRUEBAS = "pruebas_etl.hospital_registros"
PERMITIDAS = {TABLA_PRUEBAS}


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

    consulta = construir_consulta(TABLA_PRUEBAS, PERMITIDAS)

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
        TABLA_PRUEBAS,
        PERMITIDAS
    )

    assert operaciones == 1
    conexion.execute.assert_called_once()


def test_tabla_por_defecto_es_la_configurada():

    consulta = construir_consulta("public.hospital_registros")

    assert "INSERT INTO public.hospital_registros" in str(consulta)
    assert "fecha_actualizacion = CURRENT_TIMESTAMP" in str(consulta)


def test_rechazar_identificador_sospechoso():

    tabla = "public.x; DROP TABLE y"

    with pytest.raises(ValueError):
        construir_consulta(tabla, {tabla})


def test_preparar_datos_normaliza_enteros(tmp_path):

    archivo = tmp_path / "datos.csv"
    archivo.write_text(
        "numero_historia,fecha,edad,especialidad,tecnica_anestesica,"
        "duracion_minutos,hospital_origen\n"
        "002001,2026-01-15,33.0,Cirugia,General,80.0,Hospital 2\n",
        encoding="utf-8-sig",
    )

    df = preparar_datos(archivo)

    assert df.loc[0, "edad"] == 33
    assert str(df["edad"].dtype) == "int64"
    assert str(df["duracion_minutos"].dtype) == "int64"
    assert df.loc[0, "numero_historia"] == "002001"


def test_cargar_incremental_sin_registros():

    conexion = Mock()

    operaciones = cargar_incremental(pd.DataFrame(), conexion, TABLA_PRUEBAS, PERMITIDAS)

    assert operaciones == 0
    conexion.execute.assert_not_called()
