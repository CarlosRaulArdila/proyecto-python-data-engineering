
import pandas as pd

from src.validar_reglas import validar_datos


def test_aceptar_registro_valido():
    # Arrange: preparar un registro que cumple todas las reglas
    datos = pd.DataFrame({
        "numero_historia": ["001001"],
        "fecha": ["2026-01-10"],
        "edad": [35],
        "especialidad": ["Cirugia"],
        "tecnica_anestesica": ["General"],
        "duracion_minutos": [90],
        "hospital_origen": ["Hospital 1"]
    })

    # Act: ejecutar la validación
    df_validos, df_rechazados = validar_datos(datos)

    # Assert: comprobar los resultados
    assert len(df_validos) == 1
    assert len(df_rechazados) == 0

    # Comprobar que se conserva el número de historia
    assert df_validos.iloc[0]["numero_historia"] == "001001"


def test_rechazar_edades_fuera_de_rango():
    # Arrange: crear registros con edades inválidas
    datos = pd.DataFrame({
        "numero_historia": ["001002", "001003"],
        "fecha": ["2026-01-11", "2026-01-12"],
        "edad": [-5, 130],
        "especialidad": ["Cirugia", "Urologia"],
        "tecnica_anestesica": ["General", "Regional"],
        "duracion_minutos": [90, 120],
        "hospital_origen": ["Hospital 1", "Hospital 2"]
    })

    # Act: ejecutar la validación
    df_validos, df_rechazados = validar_datos(datos)

    # Assert: ambos registros deben ser rechazados
    assert len(df_validos) == 0
    assert len(df_rechazados) == 2

    # Comprobar el motivo del rechazo
    assert all(
        df_rechazados["errores_validacion"].str.contains(
            "Edad fuera del rango permitido"
        )
    )


def test_rechazar_duraciones_invalidas():
    # Arrange: crear registros con duraciones inválidas
    datos = pd.DataFrame({
        "numero_historia": ["001004", "001005"],
        "fecha": ["2026-01-13", "2026-01-14"],
        "edad": [35, 45],
        "especialidad": ["Cirugia", "Urologia"],
        "tecnica_anestesica": ["General", "Regional"],
        "duracion_minutos": [0, -30],
        "hospital_origen": ["Hospital 1", "Hospital 2"]
    })

    # Act: ejecutar la validación
    df_validos, df_rechazados = validar_datos(datos)

    # Assert: ambos registros deben ser rechazados
    assert len(df_validos) == 0
    assert len(df_rechazados) == 2

    # Comprobar el motivo del rechazo
    assert all(
        df_rechazados["errores_validacion"].str.contains(
            "Duración inválida"
        )
    )


def test_rechazar_especialidad_no_permitida():
    # Arrange: crear un registro con especialidad no permitida
    datos = pd.DataFrame({
        "numero_historia": ["001006"],
        "fecha": ["2026-01-15"],
        "edad": [35],
        "especialidad": ["Cardiologia"],
        "tecnica_anestesica": ["General"],
        "duracion_minutos": [90],
        "hospital_origen": ["Hospital 1"]
    })

    # Act: ejecutar la validación
    df_validos, df_rechazados = validar_datos(datos)

    # Assert: el registro debe ser rechazado
    assert len(df_validos) == 0
    assert len(df_rechazados) == 1

    # Comprobar el motivo del rechazo
    assert (
        "Especialidad no permitida"
        in df_rechazados.iloc[0]["errores_validacion"]
    )


def test_rechazar_tecnica_anestesica_no_permitida():
    # Arrange: crear un registro con técnica no permitida
    datos = pd.DataFrame({
        "numero_historia": ["001007"],
        "fecha": ["2026-01-16"],
        "edad": [40],
        "especialidad": ["Cirugia"],
        "tecnica_anestesica": ["Hipnosis"],
        "duracion_minutos": [90],
        "hospital_origen": ["Hospital 1"]
    })

    # Act: ejecutar la validación
    df_validos, df_rechazados = validar_datos(datos)

    # Assert: el registro debe ser rechazado
    assert len(df_validos) == 0
    assert len(df_rechazados) == 1

    # Comprobar el motivo del rechazo
    assert (
        "Técnica anestésica no permitida"
        in df_rechazados.iloc[0]["errores_validacion"]
    )


def test_rechazar_fecha_invalida():
    # Arrange: crear un registro con fecha inválida
    datos = pd.DataFrame({
        "numero_historia": ["001008"],
        "fecha": ["fecha_incorrecta"],
        "edad": [35],
        "especialidad": ["Cirugia"],
        "tecnica_anestesica": ["General"],
        "duracion_minutos": [90],
        "hospital_origen": ["Hospital 1"]
    })

    # Act: ejecutar la validación
    df_validos, df_rechazados = validar_datos(datos)

    # Assert: el registro debe ser rechazado
    assert len(df_validos) == 0
    assert len(df_rechazados) == 1

    # Comprobar el motivo del rechazo
    assert (
        "Fecha inválida"
        in df_rechazados.iloc[0]["errores_validacion"]
    )


def test_rechazar_numero_historia_vacio():
    # Arrange: crear un registro sin número de historia
    datos = pd.DataFrame({
        "numero_historia": ["   "],
        "fecha": ["2026-01-17"],
        "edad": [35],
        "especialidad": ["Cirugia"],
        "tecnica_anestesica": ["General"],
        "duracion_minutos": [90],
        "hospital_origen": ["Hospital 1"]
    })

    # Act: ejecutar la validación
    df_validos, df_rechazados = validar_datos(datos)

    # Assert: el registro debe ser rechazado
    assert len(df_validos) == 0
    assert len(df_rechazados) == 1

    # Comprobar el motivo del rechazo
    assert (
        "Número de historia vacío"
        in df_rechazados.iloc[0]["errores_validacion"]
    )


def test_rechazar_hospital_origen_vacio():
    # Arrange: crear un registro sin hospital de origen
    datos = pd.DataFrame({
        "numero_historia": ["001009"],
        "fecha": ["2026-01-18"],
        "edad": [35],
        "especialidad": ["Cirugia"],
        "tecnica_anestesica": ["General"],
        "duracion_minutos": [90],
        "hospital_origen": ["   "]
    })

    # Act: ejecutar la validación
    df_validos, df_rechazados = validar_datos(datos)

    # Assert: el registro debe ser rechazado
    assert len(df_validos) == 0
    assert len(df_rechazados) == 1

    # Comprobar el motivo del rechazo
    assert (
        "Hospital de origen vacío"
        in df_rechazados.iloc[0]["errores_validacion"]
    )


def test_rechazar_edad_decimal():
    datos = pd.DataFrame({
        "numero_historia": ["001010"],
        "fecha": ["2026-01-19"],
        "edad": [35.5],
        "especialidad": ["Cirugia"],
        "tecnica_anestesica": ["General"],
        "duracion_minutos": [90],
        "hospital_origen": ["Hospital 1"]
    })

    df_validos, df_rechazados = validar_datos(datos)

    assert len(df_validos) == 0
    assert "Edad no es un número entero" in df_rechazados.iloc[0]["errores_validacion"]


def test_aceptar_edad_entera_guardada_como_decimal():
    # 33.0 proviene de columnas con vacíos en el CSV de origen
    datos = pd.DataFrame({
        "numero_historia": ["001011"],
        "fecha": ["2026-01-20"],
        "edad": [33.0],
        "especialidad": ["Cirugia"],
        "tecnica_anestesica": ["General"],
        "duracion_minutos": [90.0],
        "hospital_origen": ["Hospital 1"]
    })

    df_validos, df_rechazados = validar_datos(datos)

    assert len(df_validos) == 1
    assert len(df_rechazados) == 0
