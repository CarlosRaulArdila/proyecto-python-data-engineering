
import logging
from datetime import date

import pandas as pd
import pytest

from src.configuracion import CONFIG
from src.esquema import construir_esquema, obtener_esquema

DEFINICION = {
    "columnas": [
        {"nombre": "codigo", "tipo": "texto", "longitud_max": 10},
        {"nombre": "fecha", "tipo": "fecha"},
        {"nombre": "cantidad", "tipo": "entero"},
        {"nombre": "precio", "tipo": "decimal", "obligatoria": False},
        {"nombre": "activo", "tipo": "booleano", "obligatoria": False},
        {"nombre": "origen", "tipo": "texto", "derivada": True},
    ]
}


@pytest.fixture
def esquema():
    return construir_esquema(DEFINICION)


def test_consultas_del_esquema(esquema):

    assert esquema.nombres == ["codigo", "fecha", "cantidad", "precio", "activo", "origen"]
    assert esquema.obligatorias == ["codigo", "fecha", "cantidad", "origen"]
    assert esquema.de_fuente == ["codigo", "fecha", "cantidad", "precio", "activo"]
    assert esquema.de_tipo("entero", "decimal") == ["cantidad", "precio"]
    assert esquema.dtypes_lectura() == {"codigo": str, "origen": str}
    assert esquema.columna("codigo").longitud_max == 10


def test_esquema_del_proyecto_es_valido():

    esquema = obtener_esquema(CONFIG)

    assert "numero_historia" in esquema.nombres
    assert esquema.columna("hospital_origen").derivada
    assert set(CONFIG["pipeline"]["clave_negocio"]) <= set(esquema.nombres)


@pytest.mark.parametrize(
    ("columnas", "mensaje"),
    [
        ([{"nombre": "a", "tipo": "numero"}], "no admitido"),
        ([{"nombre": "a"}], "requiere 'nombre' y 'tipo'"),
        ([{"nombre": "a", "tipo": "texto"}, {"nombre": "a", "tipo": "texto"}], "duplicada"),
        ([{"nombre": "a", "tipo": "texto", "obligatorio": True}], "propiedades desconocidas"),
        ([], "lista 'columnas'"),
        ([{"nombre": "Fecha Alta", "tipo": "fecha"}], "Nombre de columna"),
    ],
)
def test_definiciones_invalidas(columnas, mensaje):

    with pytest.raises(ValueError, match=mensaje):
        construir_esquema({"columnas": columnas})


def test_clave_de_negocio_fuera_del_esquema():

    config = {"esquema": DEFINICION, "pipeline": {"clave_negocio": ["codigo", "no_existe"]}}

    with pytest.raises(ValueError, match="no_existe"):
        obtener_esquema(config)


def test_fuente_sin_columna_requerida(esquema):

    df = pd.DataFrame({"codigo": ["A"], "fecha": ["2026-01-01"]})

    with pytest.raises(ValueError, match=r"ventas\.csv.*cantidad"):
        esquema.ajustar_columnas_fuente(df, "ventas.csv")


def test_fuente_con_columnas_sobrantes(esquema, caplog):

    df = pd.DataFrame({
        "extra": [1],
        "activo": ["si"],
        "precio": [1.5],
        "cantidad": [2],
        "fecha": ["2026-01-01"],
        "codigo": ["A"],
    })

    with caplog.at_level(logging.WARNING):
        resultado = esquema.ajustar_columnas_fuente(df, "ventas.csv")

    assert list(resultado.columns) == ["codigo", "fecha", "cantidad", "precio", "activo"]
    assert "extra" in caplog.text


def test_convertir_tipos(esquema):

    df = pd.DataFrame({
        "codigo": ["007"],
        "fecha": ["2026-03-15"],
        "cantidad": [4.0],
        "precio": ["10.50"],
        "activo": ["Sí"],
        "origen": ["Tienda 1"],
    })

    resultado = esquema.convertir_tipos(df)

    assert resultado.loc[0, "codigo"] == "007"
    assert resultado.loc[0, "fecha"] == date(2026, 3, 15)
    assert resultado.loc[0, "cantidad"] == 4
    assert str(resultado["cantidad"].dtype) == "int64"
    assert resultado.loc[0, "precio"] == pytest.approx(10.5)
    assert resultado["activo"].tolist() == [True]


def test_booleano_no_reconocido(esquema):

    df = pd.DataFrame({"activo": ["quizás"]})

    with pytest.raises(ValueError, match="booleano"):
        esquema.convertir_tipos(df)
