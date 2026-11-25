
import pandas as pd

from src.limpiar_datos import limpiar_datos


def test_eliminar_registros_incompletos():
    # Arrange: preparar datos de prueba
    datos = pd.DataFrame({
        "numero_historia": ["001", "002", "003"],
        "edad": [35, None, 45],
        "especialidad": ["Cirugia", "Urologia", "Traumatologia"]
    })

    # Act: ejecutar la función de limpieza
    df_limpio, df_incompletos, df_duplicados = limpiar_datos(datos)

    # Assert: comprobar los resultados
    assert len(df_limpio) == 2
    assert len(df_incompletos) == 1
    assert len(df_duplicados) == 0


def test_eliminar_duplicados_exactos():
    # Arrange: preparar datos con un duplicado
    datos = pd.DataFrame({
        "numero_historia": ["001", "002", "002"],
        "edad": [35, 40, 40],
        "especialidad": ["Cirugia", "Urologia", "Urologia"]
    })

    # Act: ejecutar la función de limpieza
    df_limpio, df_incompletos, df_duplicados = limpiar_datos(datos)

    # Assert: comprobar los resultados
    assert len(df_limpio) == 2
    assert len(df_incompletos) == 0
    assert len(df_duplicados) == 1

    # Comprobar que se conserva la primera aparición
    assert df_limpio["numero_historia"].tolist() == ["001", "002"]


def test_dataframe_vacio():
    # Arrange: crear un DataFrame vacío con las columnas esperadas
    datos = pd.DataFrame(columns=[
        "numero_historia",
        "edad",
        "especialidad"
    ])

    # Act: ejecutar la función
    df_limpio, df_incompletos, df_duplicados = limpiar_datos(datos)

    # Assert: comprobar que todos los resultados están vacíos
    assert len(df_limpio) == 0
    assert len(df_incompletos) == 0
    assert len(df_duplicados) == 0


