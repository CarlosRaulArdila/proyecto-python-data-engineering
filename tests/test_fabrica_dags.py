"""
Pruebas de la fábrica de DAG sin instalar Airflow: la lógica pura se prueba
directamente y la creación de DAG con módulos simulados de Airflow.
"""

import importlib
import sys
import types
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "dags"))

import etl_fabrica_config as fabrica  # noqa: E402


def test_especificaciones_de_los_pipelines_del_proyecto():

    specs, errores = fabrica.especificaciones(RAIZ)

    assert errores == []
    por_id = {s.dag_id: s for s in specs}

    assert set(por_id) == {"hospital_etl_pipeline", "ventas_etl_pipeline"}

    hospital = por_id["hospital_etl_pipeline"]
    assert hospital.ruta_config == "config/config.yaml"
    assert hospital.horario == "0 6 * * *"
    assert hospital.rutas_raw == ("data/raw",)

    ventas = por_id["ventas_etl_pipeline"]
    assert ventas.ruta_config == "pipelines/ventas/config.yaml"
    assert ventas.horario == "30 6 * * *"
    assert ventas.rutas_raw == ("data/ventas/raw",)


def config_minima(**orquestacion):
    return {
        "proyecto": {"nombre": "x", "entorno": "qa"},
        "pipeline": {"id": "mi_pipeline"},
        "rutas": {"raw": "data/x/raw", "processed": "data/x/p", "rejected": "data/x/r",
                  "logs": "logs/x"},
        "orquestacion": orquestacion,
    }


def test_valores_por_defecto():

    spec = fabrica.especificacion("pipelines/x/config.yaml", config_minima())

    assert spec.dag_id == "mi_pipeline"
    assert spec.horario is None
    assert spec.zona_horaria == "America/Bogota"
    assert spec.reintentos_migraciones == 2
    assert spec.ambiente == "qa"


def test_pipeline_inactivo_no_crea_dag():

    assert fabrica.especificacion("x", config_minima(activo=False)) is None


@pytest.mark.parametrize(
    ("orquestacion", "rutas", "mensaje"),
    [
        ({"horario": "cada dia"}, None, "horario inválido"),
        ({"dag_id": "con espacio"}, None, "dag_id inválido"),
        ({"horaio": "0 6 * * *"}, None, "Claves desconocidas"),
        ({}, {"raw": "C:/datos/raw"}, "rutas.raw"),
        ({}, {"processed": "../fuera"}, "rutas.processed"),
        ({}, {"logs": "/var/log"}, "rutas.logs"),
    ],
)
def test_configuraciones_invalidas(orquestacion, rutas, mensaje):

    config = config_minima(**orquestacion)
    config["rutas"].update(rutas or {})

    with pytest.raises(ValueError, match=mensaje):
        fabrica.especificacion("x", config)


@pytest.mark.parametrize("horario", ["0 6 * * *", "*/30 * * * *", "@daily", "15 2 * * 1-5"])
def test_horarios_validos(horario):

    assert fabrica.especificacion("x", config_minima(horario=horario)).horario == horario


def test_un_pipeline_invalido_no_bloquea_a_los_demas(tmp_path):

    (tmp_path / "pipelines" / "bueno").mkdir(parents=True)
    (tmp_path / "pipelines" / "malo").mkdir(parents=True)
    (tmp_path / "pipelines" / "_plantilla").mkdir(parents=True)

    bueno = config_minima()
    bueno["pipeline"]["id"] = "bueno"
    malo = config_minima(horario="nunca")
    malo["pipeline"]["id"] = "malo"

    for nombre, config in [("bueno", bueno), ("malo", malo), ("_plantilla", bueno)]:
        (tmp_path / "pipelines" / nombre / "config.yaml").write_text(
            yaml.safe_dump(config), encoding="utf-8"
        )

    specs, errores = fabrica.especificaciones(tmp_path)

    assert [s.dag_id for s in specs] == ["bueno"]
    assert len(errores) == 1 and "pipelines/malo/config.yaml" in errores[0]


def test_dag_id_duplicado(tmp_path):

    for nombre in ("a", "b"):
        (tmp_path / "pipelines" / nombre).mkdir(parents=True)
        (tmp_path / "pipelines" / nombre / "config.yaml").write_text(
            yaml.safe_dump(config_minima()), encoding="utf-8"
        )

    specs, errores = fabrica.especificaciones(tmp_path)

    assert len(specs) == 1
    assert "duplicado" in errores[0]


@pytest.mark.parametrize(
    ("task_id", "error", "esperado"),
    [
        ("ejecutar_pipeline_etl", "Docker container failed: {'StatusCode': 1, 'Error': None}",
         True),
        ("ejecutar_pipeline_etl", "Docker container failed: {'StatusCode': 137, 'Error': None}",
         False),
        ("ejecutar_pipeline_etl", "404 Client Error: No such image: hospital-etl:9.9.9", False),
        ("aplicar_migraciones", "Docker container failed: {'StatusCode': 1, 'Error': None}", False),
        ("ejecutar_pipeline_etl", None, False),
    ],
)
def test_que_fallos_avisa_airflow(task_id, error, esperado):

    excepcion = RuntimeError(error) if error else None

    assert fabrica.es_fallo_reportado_por_el_pipeline(task_id, excepcion) is esperado


# ------------------------------------------------------------------
# Creación de los DAG con Airflow simulado
# ------------------------------------------------------------------


@pytest.fixture
def airflow_simulado(monkeypatch):
    creados = []

    class DAG:
        def __init__(self, **kwargs):
            self.kwargs, self.tareas = kwargs, []
            creados.append(self)

        def __enter__(self):
            DAG.actual = self
            return self

        def __exit__(self, *args):
            DAG.actual = None

    class DockerOperator:
        def __init__(self, **kwargs):
            self.kwargs, self.siguientes = kwargs, []
            DAG.actual.tareas.append(self)

        def __rshift__(self, otra):
            self.siguientes.append(otra.kwargs["task_id"])
            return otra

    class Mount(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    modulos = {
        "airflow": types.SimpleNamespace(DAG=DAG),
        "airflow.models": types.SimpleNamespace(Variable=object),
        "airflow.providers": types.ModuleType("airflow.providers"),
        "airflow.providers.docker": types.ModuleType("airflow.providers.docker"),
        "airflow.providers.docker.operators": types.ModuleType("ops"),
        "airflow.providers.docker.operators.docker": types.SimpleNamespace(
            DockerOperator=DockerOperator
        ),
        "docker": types.ModuleType("docker"),
        "docker.types": types.SimpleNamespace(Mount=Mount),
        "pendulum": types.SimpleNamespace(datetime=lambda *a, **k: ("fecha", a, k)),
    }

    for nombre, modulo in modulos.items():
        monkeypatch.setitem(sys.modules, nombre, modulo)

    monkeypatch.setenv("ETL_CONFIGS_DIR", str(RAIZ))
    monkeypatch.setenv("ETL_PROJECT_PATH", "/host/proyecto")
    sys.modules.pop("fabrica_pipelines_etl", None)

    modulo = importlib.import_module("fabrica_pipelines_etl")
    yield modulo, creados
    sys.modules.pop("fabrica_pipelines_etl", None)


def test_la_fabrica_crea_un_dag_por_pipeline(airflow_simulado):

    modulo, creados = airflow_simulado
    por_id = {d.kwargs["dag_id"]: d for d in creados}

    assert set(por_id) == {"hospital_etl_pipeline", "ventas_etl_pipeline"}
    assert modulo.hospital_etl_pipeline is por_id["hospital_etl_pipeline"]

    ventas = por_id["ventas_etl_pipeline"]
    assert ventas.kwargs["schedule"] == "30 6 * * *"
    assert ventas.kwargs["catchup"] is False
    assert "ventas" in ventas.kwargs["tags"]

    migraciones, pipeline = ventas.tareas
    assert migraciones.kwargs["task_id"] == "aplicar_migraciones"
    assert migraciones.siguientes == ["ejecutar_pipeline_etl"]
    assert pipeline.kwargs["retries"] == 0
    assert pipeline.kwargs["image"] == f"hospital-etl:{fabrica.VERSION_MOTOR}"

    entorno = pipeline.kwargs["environment"]
    assert entorno["ETL_CONFIG_PATH"] == "pipelines/ventas/config.yaml"
    assert entorno["DB_PASSWORD"] == "{{ conn.hospital_dw_etl.password }}"
    assert entorno["ETL_SMTP_CLAVE"] == "{{ var.value.get('ETL_SMTP_PASSWORD', '') }}"

    montajes = {m["target"]: m for m in pipeline.kwargs["mounts"]}
    assert montajes["/app/data/ventas/raw"]["read_only"] is True
    assert montajes["/app/data"]["source"] == "/host/proyecto/data"


def test_la_version_del_motor_coincide_con_el_proyecto():

    from src.configuracion import CONFIG

    assert CONFIG["proyecto"]["version"] in (fabrica.VERSION_MOTOR, "2.0.0")
