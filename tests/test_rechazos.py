
import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src import rechazos
from src.rechazos import filas_de_rechazo, leer_rechazados


def test_filas_de_rechazo():

    df = pd.DataFrame({
        "numero_historia": ["001", "002"],
        "edad": ["35", None],
        "hospital_origen": ["Hospital 1", "Hospital 2"],
        "errores_validacion": ["Edad fuera del rango permitido", "Edad vacío"],
    })

    filas = filas_de_rechazo(df, "regla_negocio", "errores_validacion", "hospital_origen",
                             "run-1", "p1")

    assert [f["motivo"] for f in filas] == ["Edad fuera del rango permitido", "Edad vacío"]
    assert [f["fuente"] for f in filas] == ["Hospital 1", "Hospital 2"]
    assert all(f["run_id"] == "run-1" and f["tipo"] == "regla_negocio" for f in filas)

    registro = json.loads(filas[1]["registro"])
    assert registro == {"numero_historia": "002", "edad": None, "hospital_origen": "Hospital 2"}


def test_sin_motivo():

    df = pd.DataFrame({"a": ["1"], "motivo_rechazo": [None]})

    fila = filas_de_rechazo(df, "duplicado", "motivo_rechazo", "fuente", "r", "p")[0]

    assert fila["motivo"] == "Sin motivo informado"
    assert fila["fuente"] is None


def test_leer_rechazados_vacio_o_inexistente(tmp_path):

    vacio = tmp_path / "vacio.csv"
    vacio.write_text("", encoding="utf-8")
    solo_encabezado = tmp_path / "encabezado.csv"
    solo_encabezado.write_text("a,b\n", encoding="utf-8")

    assert leer_rechazados(tmp_path / "no_existe.csv").empty
    assert leer_rechazados(vacio).empty
    assert leer_rechazados(solo_encabezado).empty


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    conexion = MagicMock()
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = conexion
    monkeypatch.setattr("src.conexion_db.obtener_engine", lambda: engine)
    monkeypatch.setattr(rechazos, "REJECTED_DIR", tmp_path)
    return conexion, tmp_path


def test_registrar_rechazos_lee_todos_los_tipos(entorno):

    conexion, carpeta = entorno
    archivos = rechazos.CONFIG["archivos"]

    pd.DataFrame({"numero_historia": ["1"], "hospital_origen": ["H1"],
                  "motivo_rechazo": ["Campos obligatorios vacíos: edad"]}
                 ).to_csv(carpeta / archivos["incompletos"], index=False)
    pd.DataFrame({"numero_historia": ["2", "3"], "hospital_origen": ["H2", "H2"],
                  "errores_validacion": ["x", "y"]}
                 ).to_csv(carpeta / archivos["fuera_reglas"], index=False)

    resultado = rechazos.registrar_rechazos({"run_id": "r1", "pipeline_id": "p"})

    assert resultado == {"rechazos_registrados": 3}
    filas = conexion.execute.call_args.args[1]
    assert sorted(f["tipo"] for f in filas) == ["incompleto", "regla_negocio", "regla_negocio"]


def test_registrar_rechazos_sin_rechazados(entorno):

    conexion, _ = entorno

    assert rechazos.registrar_rechazos({"run_id": "r1"}) == {"rechazos_registrados": 0}
    conexion.execute.assert_not_called()


def test_registrar_rechazos_exige_run_id():

    with pytest.raises(RuntimeError, match="run_id"):
        rechazos.registrar_rechazos({})


def test_tabla_configurada():

    assert rechazos.TABLA_RECHAZOS == "public.etl_rechazos"
