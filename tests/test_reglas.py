
import pandas as pd
import pytest

from src.esquema import construir_esquema
from src.reglas import construir_reglas, validar_dataframe

ESQUEMA = construir_esquema({
    "columnas": [
        {"nombre": "codigo", "tipo": "texto", "etiqueta": "Código", "longitud_max": 8},
        {"nombre": "fecha", "tipo": "fecha", "etiqueta": "Fecha"},
        {"nombre": "unidades", "tipo": "entero", "etiqueta": "Unidades"},
        {"nombre": "precio", "tipo": "decimal", "etiqueta": "Precio", "obligatoria": False},
        {"nombre": "canal", "tipo": "texto", "etiqueta": "Canal"},
    ]
})

REGLAS = construir_reglas(
    [
        {"columna": "unidades", "tipo": "rango", "min": 1, "max": 100,
         "mensaje": "Unidades fuera de rango"},
        {"columna": "precio", "tipo": "rango", "min": 0, "min_inclusivo": False,
         "mensaje": "Precio debe ser positivo"},
        {"columna": "canal", "tipo": "valores_permitidos", "valores": ["web", "tienda"],
         "mensaje": "Canal no permitido"},
        {"columna": "codigo", "tipo": "patron", "patron": r"[A-Z]{3}-\d{3}",
         "mensaje": "Código con formato inválido"},
    ],
    ESQUEMA,
)


def fila(**cambios):
    base = {
        "codigo": "ABC-123",
        "fecha": "2026-03-01",
        "unidades": 5,
        "precio": 9.9,
        "canal": "web",
    }
    base.update(cambios)
    return base


def validar(*filas):
    return validar_dataframe(pd.DataFrame(list(filas)), ESQUEMA, REGLAS)


def errores(df_rechazados):
    return df_rechazados["errores_validacion"].tolist()


def test_registro_valido():

    validos, rechazados = validar(fila())

    assert len(validos) == 1
    assert len(rechazados) == 0
    assert "errores_validacion" not in validos.columns


def test_rango_inclusivo_y_exclusivo():

    _, rechazados = validar(
        fila(unidades=1),      # límite inclusivo: válido
        fila(unidades=101),    # fuera
        fila(precio=0),        # 0 excluido
    )

    assert errores(rechazados) == ["Unidades fuera de rango", "Precio debe ser positivo"]


def test_valores_permitidos_y_patron():

    _, rechazados = validar(fila(canal="telefono"), fila(codigo="AB-1"))

    assert errores(rechazados) == ["Canal no permitido", "Código con formato inválido"]


def test_reglas_automaticas_del_esquema():

    _, rechazados = validar(
        fila(codigo="   "),
        fila(fecha="31/02/xx"),
        fila(unidades="muchas"),
        fila(unidades=2.5),
        fila(codigo="ABCDE-12345"),
    )

    mensajes = errores(rechazados)

    assert "Código vacío" in mensajes[0]
    assert mensajes[1] == "Fecha inválida"
    assert mensajes[2] == "Unidades no es un número"
    assert mensajes[3] == "Unidades no es un número entero"
    assert "Código supera 8 caracteres" in mensajes[4]


def test_columna_opcional_vacia_es_valida():

    validos, _ = validar(fila(precio=None))

    assert len(validos) == 1


def test_varios_motivos_en_un_registro():

    _, rechazados = validar(fila(unidades=0, canal="fax"))

    assert errores(rechazados) == ["Unidades fuera de rango; Canal no permitido"]


def test_conserva_el_indice_original():

    df = pd.DataFrame([fila(), fila(canal="fax")], index=[10, 20])

    validos, rechazados = validar_dataframe(df, ESQUEMA, REGLAS)

    assert validos.index.tolist() == [10]
    assert rechazados.index.tolist() == [20]


@pytest.mark.parametrize(
    ("definicion", "mensaje"),
    [
        ({"columna": "x", "tipo": "rango", "min": 1, "mensaje": "m"}, "no está en el esquema"),
        ({"columna": "unidades", "tipo": "maximo", "mensaje": "m"}, "no admitido"),
        ({"columna": "unidades", "tipo": "rango", "mensaje": "m"}, "'min', 'max' o ambos"),
        ({"columna": "canal", "tipo": "rango", "min": 1, "mensaje": "m"}, "columnas numéricas"),
        ({"columna": "canal", "tipo": "valores_permitidos", "mensaje": "m"}, "requiere"),
        ({"columna": "unidades", "tipo": "rango", "min": 1, "minimo": 2, "mensaje": "m"},
         "desconocidos"),
        ({"columna": "codigo", "tipo": "patron", "patron": "[", "mensaje": "m"},
         "Patrón inválido"),
        ({"columna": "unidades", "tipo": "rango", "min": 1}, "le faltan"),
    ],
)
def test_reglas_mal_definidas(definicion, mensaje):

    with pytest.raises(ValueError, match=mensaje):
        construir_reglas([definicion], ESQUEMA)


def test_sin_reglas_de_negocio_solo_aplica_el_esquema():

    validos, rechazados = validar_dataframe(
        pd.DataFrame([fila(canal="cualquiera")]), ESQUEMA, construir_reglas(None, ESQUEMA)
    )

    assert len(validos) == 1
    assert len(rechazados) == 0


def test_reglas_del_proyecto_son_validas():

    from src.configuracion import CONFIG
    from src.esquema import obtener_esquema

    reglas = construir_reglas(CONFIG["reglas"], obtener_esquema(CONFIG))

    assert {r.tipo for r in reglas} == {"rango", "valores_permitidos"}
