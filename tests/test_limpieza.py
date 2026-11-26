
import pandas as pd
import pytest

from src.limpiar_datos import limpiar_datos, separar_conflictos_clave

CLAVE = ["numero_historia", "fecha", "hospital_origen"]


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


def test_conflicto_de_clave_rechaza_todas_las_versiones():
    # Arrange: misma clave de negocio con edades distintas
    datos = pd.DataFrame({
        "numero_historia": ["001", "001", "002"],
        "fecha": ["2026-01-10", "2026-01-10", "2026-01-11"],
        "hospital_origen": ["H1", "H1", "H1"],
        "edad": [35, 36, 40],
    })

    # Act
    df_ok, df_conflictos = separar_conflictos_clave(datos, CLAVE)

    # Assert: ninguna versión del registro 001 se carga
    assert df_ok["numero_historia"].tolist() == ["002"]
    assert len(df_conflictos) == 2
    assert df_conflictos["motivo_rechazo"].str.contains("Clave de negocio").all()


def test_misma_historia_en_otra_fecha_no_es_conflicto():
    datos = pd.DataFrame({
        "numero_historia": ["001", "001"],
        "fecha": ["2026-01-10", "2026-01-11"],
        "hospital_origen": ["H1", "H1"],
        "edad": [35, 35],
    })

    df_ok, df_conflictos = separar_conflictos_clave(datos, CLAVE)

    assert len(df_ok) == 2
    assert len(df_conflictos) == 0


def test_conflicto_clave_columnas_faltantes():
    datos = pd.DataFrame({"numero_historia": ["001"]})

    with pytest.raises(ValueError, match="clave de negocio"):
        separar_conflictos_clave(datos, CLAVE)
