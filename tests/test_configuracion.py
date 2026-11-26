
import copy

import pytest

from src.configuracion import CONFIG, validar_configuracion


@pytest.mark.parametrize("clave", [None, [], "numero_historia"])
def test_clave_de_negocio_obligatoria(clave):

    config = copy.deepcopy(CONFIG)
    config["pipeline"]["clave_negocio"] = clave

    with pytest.raises(ValueError, match="clave_negocio"):
        validar_configuracion(config)


def test_seccion_faltante():

    config = copy.deepcopy(CONFIG)
    del config["esquema"]

    with pytest.raises(ValueError, match="esquema"):
        validar_configuracion(config)


def test_configuracion_del_proyecto_es_valida():

    validar_configuracion(CONFIG)


def test_columna_fuente_obligatoria():

    config = copy.deepcopy(CONFIG)
    del config["pipeline"]["columna_fuente"]

    with pytest.raises(ValueError, match="columna_fuente"):
        validar_configuracion(config)


def test_columna_fuente_debe_ser_derivada():

    config = copy.deepcopy(CONFIG)
    config["pipeline"]["columna_fuente"] = "especialidad"

    with pytest.raises(ValueError, match="derivada: true"):
        validar_configuracion(config)
