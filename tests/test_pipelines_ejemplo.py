"""Los pipelines de ejemplo de pipelines/ deben tener una configuración válida."""

from pathlib import Path

import pytest

from src.configuracion import BASE_DIR, cargar_configuracion, resolver_ruta
from src.esquema import obtener_esquema
from src.reglas import construir_reglas

PIPELINES = sorted((BASE_DIR / "pipelines").glob("*/config.yaml"))


@pytest.mark.parametrize("ruta", PIPELINES, ids=lambda p: p.parent.name)
def test_configuracion_valida(ruta: Path):

    config = cargar_configuracion(ruta)
    esquema = obtener_esquema(config)

    construir_reglas(config.get("reglas"), esquema)

    assert resolver_ruta(config["migraciones"]["directorio"]).is_dir()
    assert config["pipeline"]["tareas"][-1]["funcion"] == "registrar_ingesta"

    nombres = [t["nombre"] for t in config["pipeline"]["tareas"]]
    assert nombres.index("evaluar_calidad") < nombres.index("cargar_incremental")


def test_existe_el_pipeline_de_ventas():

    assert any(p.parent.name == "ventas" for p in PIPELINES)
