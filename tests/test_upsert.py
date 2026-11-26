
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.cargar_incremental import (
    DefinicionUpsert,
    cargar_incremental,
    construir_consulta,
    definicion_desde_config,
    verificar_tabla_destino,
)
from src.sql_utils import nombre_tabla, validar_identificador

TABLA = "ventas.pedidos"
PERMITIDAS = {TABLA}


def sql(definicion):
    return " ".join(str(construir_consulta(TABLA, PERMITIDAS, definicion)).split())


def test_upsert_generado_desde_la_definicion():

    consulta = sql(DefinicionUpsert(
        columnas=("pedido", "tienda", "monto"),
        clave=("pedido", "tienda"),
        actualizables=("monto",),
        columna_actualizacion="actualizado_en",
    ))

    assert "INSERT INTO ventas.pedidos AS destino (pedido, tienda, monto)" in consulta
    assert "VALUES (:pedido, :tienda, :monto)" in consulta
    assert "ON CONFLICT (pedido, tienda)" in consulta
    assert "monto = EXCLUDED.monto, actualizado_en = CURRENT_TIMESTAMP" in consulta
    assert "WHERE destino.monto IS DISTINCT FROM EXCLUDED.monto" in consulta


def test_sin_columnas_actualizables_no_hace_nada_al_repetir():

    consulta = sql(DefinicionUpsert(columnas=("codigo",), clave=("codigo",), actualizables=()))

    assert consulta.endswith("ON CONFLICT (codigo) DO NOTHING;")


def test_sin_columna_de_actualizacion():

    consulta = sql(DefinicionUpsert(columnas=("a", "b"), clave=("a",), actualizables=("b",)))

    assert "CURRENT_TIMESTAMP" not in consulta


@pytest.mark.parametrize(
    ("argumentos", "mensaje"),
    [
        ({"columnas": ("a",), "clave": (), "actualizables": ()}, "no puede estar vacía"),
        ({"columnas": ("a",), "clave": ("x",), "actualizables": ()}, "fuera del esquema"),
        ({"columnas": ("a", "b"), "clave": ("a",), "actualizables": ("a",)},
         "clave y actualizable"),
        ({"columnas": ("a", "B-1"), "clave": ("a",), "actualizables": ()}, "inválido"),
        ({"columnas": ("a",), "clave": ("a",), "actualizables": (),
          "columna_actualizacion": "x;--"}, "inválido"),
    ],
)
def test_definiciones_invalidas(argumentos, mensaje):

    with pytest.raises(ValueError, match=mensaje):
        DefinicionUpsert(**argumentos)


def test_definicion_del_proyecto():

    definicion = definicion_desde_config()

    assert definicion.clave == ("numero_historia", "fecha", "hospital_origen")
    assert definicion.actualizables == (
        "edad", "especialidad", "tecnica_anestesica", "duracion_minutos"
    )
    assert definicion.columna_actualizacion == "fecha_actualizacion"


def test_columnas_actualizables_configurables():

    from src.configuracion import CONFIG

    config = {**CONFIG, "base_datos": {**CONFIG["base_datos"], "columnas_actualizables": ["edad"]}}

    assert definicion_desde_config(config).actualizables == ("edad",)


def test_cargar_solo_envia_columnas_del_esquema():

    definicion = DefinicionUpsert(columnas=("a", "b"), clave=("a",), actualizables=("b",))
    df = pd.DataFrame([{"b": 2, "a": 1, "sobrante": "x"}])
    conexion = MagicMock()
    conexion.execute.return_value.rowcount = 1

    cargar_incremental(df, conexion, TABLA, PERMITIDAS, definicion)

    registros = conexion.execute.call_args.args[1]
    assert registros == [{"a": 1, "b": 2}]


def conexion_con_columnas(columnas):
    conexion = MagicMock()
    conexion.execute.return_value.scalars.return_value = columnas
    return conexion


def test_verificar_tabla_destino_correcta():

    definicion = DefinicionUpsert(
        columnas=("a", "b"), clave=("a",), actualizables=("b",), columna_actualizacion="c"
    )

    verificar_tabla_destino(conexion_con_columnas(["id", "a", "b", "c"]), TABLA, definicion)


def test_verificar_tabla_destino_sin_columnas():

    definicion = DefinicionUpsert(
        columnas=("a", "b"), clave=("a",), actualizables=("b",), columna_actualizacion="c"
    )

    with pytest.raises(ValueError, match=r"\['b', 'c'\]"):
        verificar_tabla_destino(conexion_con_columnas(["a"]), TABLA, definicion)


def test_verificar_tabla_destino_inexistente():

    definicion = DefinicionUpsert(columnas=("a",), clave=("a",), actualizables=())

    with pytest.raises(ValueError, match="no existe"):
        verificar_tabla_destino(conexion_con_columnas([]), TABLA, definicion)


@pytest.mark.parametrize("nombre", ["hospital_registros", "_tmp", "t1"])
def test_identificadores_validos(nombre):

    assert validar_identificador(nombre) == nombre


@pytest.mark.parametrize(
    "nombre", ["Tabla", "1tabla", "x;drop", "con espacio", "", "a" * 64, None]
)
def test_identificadores_invalidos(nombre):

    with pytest.raises(ValueError):
        validar_identificador(nombre)


def test_nombre_tabla():

    assert nombre_tabla("public", "etl_auditoria") == "public.etl_auditoria"


def test_auditoria_usa_la_tabla_configurada():

    from src import auditoria
    from src.configuracion import CONFIG

    esperado = f"{CONFIG['base_datos']['esquema']}.{CONFIG['base_datos']['tabla_auditoria']}"

    assert auditoria.TABLA_AUDITORIA == esperado
