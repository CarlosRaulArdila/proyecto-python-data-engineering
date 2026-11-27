
from unittest.mock import MagicMock

import pytest

from src import ejecutar_pipeline as orquestador
from src.ejecutar_pipeline import Tarea, acumular_metricas, resolver_tarea


@pytest.fixture
def auditoria_simulada(monkeypatch, tmp_path):
    """Sustituye la auditoría en base de datos y el destino de los logs."""

    inicio = MagicMock(return_value=42)
    fin = MagicMock()

    monkeypatch.setattr(orquestador.auditoria, "registrar_inicio", inicio)
    monkeypatch.setattr(orquestador.auditoria, "registrar_fin", fin)
    monkeypatch.setattr(
        orquestador, "configurar_logging", lambda run_id: tmp_path / "pipeline.log"
    )
    monkeypatch.setattr(orquestador, "cerrar_engine", lambda: None)

    notificaciones = []
    monkeypatch.setattr(orquestador.alertas, "notificar", notificaciones.append)
    fin.notificaciones = notificaciones

    return inicio, fin


def test_ejecucion_exitosa_acumula_metricas(auditoria_simulada):

    inicio, fin = auditoria_simulada

    tareas = [
        Tarea("consolidar", lambda: {"registros_extraidos": 15}),
        Tarea("limpiar", lambda: {"registros_limpios": 12, "registros_rechazados": 3}),
        Tarea("validar", lambda: {"registros_rechazados": 1, "registros_validos": 11}),
        Tarea("cargar", lambda: {"operaciones_bd": 11}),
    ]

    codigo = orquestador.ejecutar_pipeline(tareas)

    assert codigo == 0
    inicio.assert_called_once()

    argumentos = fin.call_args.kwargs
    assert argumentos["id_ejecucion"] == 42
    assert argumentos["estado"] == "EXITOSO"
    assert argumentos["registros_extraidos"] == 15
    assert argumentos["registros_limpios"] == 12
    assert argumentos["registros_rechazados"] == 4
    assert argumentos["operaciones_bd"] == 11
    assert argumentos["mensaje_error"] is None


def test_fallo_de_tarea_detiene_y_audita(auditoria_simulada):

    _, fin = auditoria_simulada
    tarea_posterior = MagicMock(return_value={})

    def tarea_que_falla():
        raise FileNotFoundError("no existe hospital_1.csv")

    tareas = [
        Tarea("consolidar", lambda: {"registros_extraidos": 5}),
        Tarea("limpiar", tarea_que_falla),
        Tarea("validar", tarea_posterior),
    ]

    codigo = orquestador.ejecutar_pipeline(tareas)

    assert codigo == 1
    tarea_posterior.assert_not_called()

    argumentos = fin.call_args.kwargs
    assert argumentos["estado"] == "FALLIDO"
    assert argumentos["registros_extraidos"] == 5
    assert "limpiar: no existe hospital_1.csv" in argumentos["mensaje_error"]


def test_sin_auditoria_no_se_ejecuta_el_pipeline(auditoria_simulada):

    inicio, fin = auditoria_simulada
    inicio.side_effect = ConnectionError("PostgreSQL no disponible")
    tarea = MagicMock(return_value={})

    codigo = orquestador.ejecutar_pipeline([Tarea("consolidar", tarea)])

    assert codigo == 1
    tarea.assert_not_called()
    fin.assert_not_called()


def test_continuar_si_falla_termina_parcial(auditoria_simulada, monkeypatch):

    _, fin = auditoria_simulada
    monkeypatch.setitem(orquestador.CONFIG["pipeline"], "detener_si_falla", False)

    def tarea_que_falla():
        raise ValueError("error puntual")

    tarea_posterior = MagicMock(return_value={"operaciones_bd": 2})

    codigo = orquestador.ejecutar_pipeline(
        [Tarea("a", tarea_que_falla), Tarea("b", tarea_posterior)]
    )

    assert codigo == 1
    tarea_posterior.assert_called_once()
    assert fin.call_args.kwargs["estado"] == "PARCIAL"
    assert fin.call_args.kwargs["operaciones_bd"] == 2


def test_fallo_al_cerrar_auditoria_devuelve_error(auditoria_simulada):

    _, fin = auditoria_simulada
    fin.side_effect = RuntimeError("conexión perdida")

    codigo = orquestador.ejecutar_pipeline([Tarea("a", lambda: {})])

    assert codigo == 1


def test_acumular_metricas_ignora_claves_desconocidas():

    totales = {"registros_rechazados": 2}

    acumular_metricas(totales, {"registros_rechazados": 3, "otra": 9})
    acumular_metricas(totales, None)

    assert totales == {"registros_rechazados": 5}


def test_resolver_tarea_desde_config():

    tarea = resolver_tarea({
        "nombre": "limpiar",
        "modulo": "src.limpiar_datos",
        "funcion": "ejecutar_limpieza",
    })

    assert tarea.nombre == "limpiar"
    assert callable(tarea.funcion)


def test_resolver_tarea_formato_antiguo_da_error_claro():

    with pytest.raises(ValueError, match="nombre', 'modulo' y 'funcion"):
        resolver_tarea("limpiar_datos.py")


def test_resolver_tarea_funcion_inexistente():

    with pytest.raises(ValueError, match="no existe"):
        resolver_tarea({
            "nombre": "x",
            "modulo": "src.limpiar_datos",
            "funcion": "no_existe",
        })


def test_todas_las_tareas_de_config_son_resolubles():

    for definicion in orquestador.CONFIG["pipeline"]["tareas"]:
        assert callable(resolver_tarea(definicion).funcion)


def test_las_tareas_reciben_el_contexto_si_lo_aceptan(auditoria_simulada):

    recibido = {}

    def con_contexto(contexto):
        recibido.update(contexto)
        return {}

    codigo = orquestador.ejecutar_pipeline(
        [Tarea("sin", lambda: {}), Tarea("con", con_contexto)]
    )

    assert codigo == 0
    assert recibido["id_ejecucion"] == 42
    assert recibido["pipeline_id"] == "hospital_etl_pipeline"
    assert len(recibido["run_id"]) == 36
    assert recibido["errores"] == []


def test_la_ultima_tarea_es_registrar_ingesta():

    assert orquestador.CONFIG["pipeline"]["tareas"][-1]["funcion"] == "registrar_ingesta"


def test_advertencias_llegan_a_la_auditoria(auditoria_simulada):

    _, fin = auditoria_simulada

    def advierte(contexto):
        contexto["advertencias"].append("Umbral de calidad: algo")
        return {}

    codigo = orquestador.ejecutar_pipeline([Tarea("calidad", advierte)])

    assert codigo == 0
    assert fin.call_args.kwargs["estado"] == "EXITOSO"
    assert fin.call_args.kwargs["advertencias"] == "Umbral de calidad: algo"


def test_detalle_de_metricas_en_el_contexto(auditoria_simulada):

    visto = {}

    def lee(contexto):
        visto.update(contexto["detalle"])
        visto["extraidos"] = contexto["metricas"]["registros_extraidos"]
        return {}

    orquestador.ejecutar_pipeline([
        Tarea("a", lambda: {"registros_extraidos": 7, "archivos_procesados": 2}),
        Tarea("b", lee),
    ])

    assert visto == {"registros_extraidos": 7, "archivos_procesados": 2, "extraidos": 7}


def test_se_notifica_el_resultado_de_la_ejecucion(auditoria_simulada):

    _, fin = auditoria_simulada

    def falla():
        raise ValueError("archivo corrupto")

    orquestador.ejecutar_pipeline([Tarea("consolidar", falla)])

    resumen = fin.notificaciones[0]
    assert resumen["estado"] == "FALLIDO"
    assert resumen["id_ejecucion"] == 42
    assert "consolidar: archivo corrupto" in resumen["mensaje_error"]
    assert resumen["pipeline_id"] == "hospital_etl_pipeline"
