
import hashlib
import logging
from unittest.mock import MagicMock

import pytest

from src import ingesta
from src.ingesta import (
    archivos_no_configurados,
    calcular_hash,
    descubrir_archivos,
    entrada_manifiesto,
    escribir_manifiesto,
    filtrar_nuevos,
    leer_manifiesto,
    modo_ingesta,
    validar_fuentes,
)


def crear(raw, nombre, contenido="a,b\n1,2\n"):
    ruta = raw / nombre
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def test_calcular_hash(tmp_path):

    ruta = crear(tmp_path, "x.csv", "hola")

    assert calcular_hash(ruta) == hashlib.sha256(b"hola").hexdigest()


def test_descubrir_por_archivo_y_por_patron(tmp_path):

    crear(tmp_path, "h1.csv")
    crear(tmp_path, "h2_lote_b.csv", "b")
    crear(tmp_path, "h2_lote_a.csv", "a")

    archivos = descubrir_archivos(
        [{"nombre": "H1", "archivo": "h1.csv"}, {"nombre": "H2", "patron": "h2_*.csv"}],
        tmp_path,
    )

    assert [(a.fuente, a.nombre) for a in archivos] == [
        ("H1", "h1.csv"),
        ("H2", "h2_lote_a.csv"),
        ("H2", "h2_lote_b.csv"),
    ]
    assert all(len(a.hash_sha256) == 64 for a in archivos)


def test_archivo_exacto_inexistente(tmp_path):

    with pytest.raises(FileNotFoundError, match="h1.csv"):
        descubrir_archivos([{"nombre": "H1", "archivo": "h1.csv"}], tmp_path)


def test_patron_sin_archivos_solo_avisa(tmp_path, caplog):

    with caplog.at_level(logging.WARNING):
        archivos = descubrir_archivos([{"nombre": "H9", "patron": "h9_*.csv"}], tmp_path)

    assert archivos == []
    assert "h9_*.csv" in caplog.text


def test_archivo_en_dos_fuentes(tmp_path):

    crear(tmp_path, "h1_2026.csv")

    with pytest.raises(ValueError, match="dos fuentes"):
        descubrir_archivos(
            [{"nombre": "A", "patron": "h1_*.csv"}, {"nombre": "B", "patron": "*.csv"}],
            tmp_path,
        )


@pytest.mark.parametrize(
    ("fuentes", "mensaje"),
    [
        ([{"archivo": "a.csv"}], "no tiene 'nombre'"),
        ([{"nombre": "A"}], "'archivo' o 'patron'"),
        ([{"nombre": "A", "archivo": "a.csv", "patron": "*.csv"}], "solo uno"),
        ([{"nombre": "A", "archivo": "a.csv"}, {"nombre": "A", "archivo": "b.csv"}],
         "duplicada"),
    ],
)
def test_fuentes_invalidas(fuentes, mensaje):

    with pytest.raises(ValueError, match=mensaje):
        validar_fuentes(fuentes)


def test_archivos_no_configurados_con_patrones(tmp_path):

    for nombre in ("h1.csv", "h2_lote.csv", "otro.csv"):
        crear(tmp_path, nombre)

    resultado = archivos_no_configurados(
        [{"nombre": "H1", "archivo": "h1.csv"}, {"nombre": "H2", "patron": "h2_*.csv"}],
        tmp_path,
    )

    assert resultado == ["otro.csv"]


def test_filtrar_nuevos_omite_procesados_y_duplicados_del_lote(tmp_path):

    a = crear(tmp_path, "a.csv", "uno")
    b = crear(tmp_path, "b.csv", "dos")
    crear(tmp_path, "b_copia.csv", "dos")

    archivos = descubrir_archivos([{"nombre": "X", "patron": "*.csv"}], tmp_path)

    nuevos, omitidos = filtrar_nuevos(archivos, {calcular_hash(a)})

    assert [x.nombre for x in nuevos] == [b.name]
    assert sorted(x.nombre for x in omitidos) == ["a.csv", "b_copia.csv"]


def test_modo_ingesta():

    assert modo_ingesta({}) == "completa"
    assert modo_ingesta({"ingesta": {"modo": "incremental"}}) == "incremental"

    with pytest.raises(ValueError, match="ingesta.modo"):
        modo_ingesta({"ingesta": {"modo": "diaria"}})


def test_manifiesto_ida_y_vuelta(tmp_path):

    crear(tmp_path, "h1.csv")
    archivo = descubrir_archivos([{"nombre": "H1", "archivo": "h1.csv"}], tmp_path)[0]
    ruta = tmp_path / "proc" / "manifiesto.json"

    escribir_manifiesto([entrada_manifiesto(archivo, 7)], "run-1", ruta)
    contenido = leer_manifiesto(ruta)

    assert contenido["run_id"] == "run-1"
    assert contenido["archivos"][0]["nombre_archivo"] == "h1.csv"
    assert contenido["archivos"][0]["registros"] == 7


@pytest.fixture
def engine_simulado(monkeypatch):
    conexion = MagicMock()
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = conexion
    monkeypatch.setattr("src.conexion_db.obtener_engine", lambda: engine)
    return conexion


def test_registrar_ingesta_omite_si_hubo_errores(engine_simulado):

    assert ingesta.registrar_ingesta({"errores": ["cargar: falló"]}) == {}
    engine_simulado.execute.assert_not_called()


def test_registrar_ingesta_inserta_el_manifiesto(engine_simulado, tmp_path, monkeypatch):

    crear(tmp_path, "h1.csv")
    archivo = descubrir_archivos([{"nombre": "H1", "archivo": "h1.csv"}], tmp_path)[0]
    ruta = tmp_path / "manifiesto.json"
    escribir_manifiesto([entrada_manifiesto(archivo, 5)], "run-1", ruta)
    monkeypatch.setattr(ingesta, "RUTA_MANIFIESTO", ruta)

    resultado = ingesta.registrar_ingesta(
        {"run_id": "run-1", "pipeline_id": "p", "errores": []}
    )

    assert resultado == {"archivos_registrados": 1}
    filas = engine_simulado.execute.call_args.args[1]
    assert filas[0]["pipeline_id"] == "p"
    assert filas[0]["run_id"] == "run-1"
    assert filas[0]["registros"] == 5


def test_registrar_ingesta_rechaza_manifiesto_de_otra_ejecucion(tmp_path, monkeypatch):

    ruta = tmp_path / "manifiesto.json"
    escribir_manifiesto([], "run-viejo", ruta)
    monkeypatch.setattr(ingesta, "RUTA_MANIFIESTO", ruta)

    with pytest.raises(RuntimeError, match="otra ejecución"):
        ingesta.registrar_ingesta({"run_id": "run-nuevo", "errores": []})


def test_registrar_ingesta_sin_archivos(engine_simulado, tmp_path, monkeypatch):

    ruta = tmp_path / "manifiesto.json"
    escribir_manifiesto([], "run-1", ruta)
    monkeypatch.setattr(ingesta, "RUTA_MANIFIESTO", ruta)

    assert ingesta.registrar_ingesta({"run_id": "run-1", "errores": []}) == {}
    engine_simulado.execute.assert_not_called()
