
import pytest

from src import calidad
from src.calidad import (
    UmbralCalidadExcedido,
    evaluar_calidad,
    evaluar_umbrales,
    validar_config_calidad,
)


def test_sin_incumplimientos():

    assert evaluar_umbrales(
        {"registros_extraidos": 100, "registros_rechazados": 30},
        {"max_porcentaje_rechazo": 30, "min_registros_extraidos": 100},
    ) == []


def test_porcentaje_de_rechazo_excedido():

    resultado = evaluar_umbrales(
        {"registros_extraidos": 15, "registros_rechazados": 3},
        {"max_porcentaje_rechazo": 10},
    )

    assert resultado == [
        "Se rechazó el 20.0 % de los registros (3 de 15); el máximo permitido es 10 %"
    ]


def test_minimo_de_registros():

    resultado = evaluar_umbrales(
        {"registros_extraidos": 2, "registros_rechazados": 0},
        {"min_registros_extraidos": 10},
    )

    assert resultado == ["Se extrajeron 2 registros; el mínimo esperado es 10"]


def test_cero_extraidos_no_divide_por_cero():

    assert evaluar_umbrales(
        {"registros_extraidos": 0, "registros_rechazados": 0},
        {"max_porcentaje_rechazo": 10},
    ) == []


@pytest.mark.parametrize(
    ("config", "mensaje"),
    [
        ({"accion": "ignorar"}, "accion inválida"),
        ({"max_porcentaje_rechazo": 120}, "entre 0 y 100"),
        ({"max_porcentaje_rechazo": "30"}, "entre 0 y 100"),
        ({"min_registros_extraidos": -1}, "mayor o igual a 0"),
        ({"maximo": 10}, "desconocidas"),
    ],
)
def test_configuracion_invalida(config, mensaje):

    with pytest.raises(ValueError, match=mensaje):
        validar_config_calidad(config)


def test_accion_por_defecto_es_fallar():

    assert validar_config_calidad({"max_porcentaje_rechazo": 5})["accion"] == "fallar"
    assert validar_config_calidad(None) == {}


@pytest.fixture
def con_calidad(monkeypatch):
    def configurar(seccion):
        from src.configuracion import CONFIG

        monkeypatch.setitem(CONFIG, "calidad", seccion)

    return configurar


def contexto(extraidos, rechazados, archivos=1):
    return {
        "metricas": {"registros_extraidos": extraidos, "registros_rechazados": rechazados},
        "detalle": {"archivos_procesados": archivos},
        "advertencias": [],
    }


def test_etapa_falla_antes_de_cargar(con_calidad):

    con_calidad({"max_porcentaje_rechazo": 10, "accion": "fallar"})

    with pytest.raises(UmbralCalidadExcedido, match="No se cargaron datos"):
        evaluar_calidad(contexto(10, 5))


def test_etapa_advierte_y_continua(con_calidad):

    con_calidad({"max_porcentaje_rechazo": 10, "accion": "advertir"})
    ctx = contexto(10, 5)

    assert evaluar_calidad(ctx) == {}
    assert ctx["advertencias"] == [
        "Umbral de calidad: Se rechazó el 50.0 % de los registros (5 de 10); "
        "el máximo permitido es 10 %"
    ]


def test_etapa_sin_archivos_nuevos_no_evalua(con_calidad):

    con_calidad({"min_registros_extraidos": 10, "accion": "fallar"})

    assert evaluar_calidad(contexto(0, 0, archivos=0)) == {}


def test_etapa_sin_seccion_calidad(monkeypatch):

    from src.configuracion import CONFIG

    monkeypatch.delitem(CONFIG, "calidad", raising=False)

    assert calidad.evaluar_calidad(contexto(10, 10)) == {}


def test_config_del_proyecto_tiene_la_etapa_antes_de_la_carga():

    from src.configuracion import CONFIG

    nombres = [t["nombre"] for t in CONFIG["pipeline"]["tareas"]]

    assert nombres.index("evaluar_calidad") < nombres.index("cargar_incremental")
