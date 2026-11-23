
import pandas as pd
from src.limpiar_datos import limpiar_datos
from src.validar_reglas import validar_datos
from src.consolidar_datos import consolidar_datos


def test_consolidar_datos_de_tres_hospitales(tmp_path):

    # Arrange: crear archivos CSV temporales
    hospital_1 = pd.DataFrame({
        "numero_historia": ["001001", "001002"],
        "edad": [35, 42]
    })

    hospital_2 = pd.DataFrame({
        "numero_historia": ["002001"],
        "edad": [50]
    })

    hospital_3 = pd.DataFrame({
        "numero_historia": ["003001", "003002"],
        "edad": [29, 60]
    })

    hospital_1.to_csv(tmp_path / "hospital_1.csv", index=False)
    hospital_2.to_csv(tmp_path / "hospital_2.csv", index=False)
    hospital_3.to_csv(tmp_path / "hospital_3.csv", index=False)

    archivos = {
        "hospital_1.csv": "Hospital 1",
        "hospital_2.csv": "Hospital 2",
        "hospital_3.csv": "Hospital 3"
    }

    # Act: consolidar los tres hospitales
    df = consolidar_datos(archivos, tmp_path)

    # Assert: comprobar los resultados
    assert len(df) == 5
    assert len(df.columns) == 3

    assert df["hospital_origen"].nunique() == 3

    # Comprobar que se conservan los ceros iniciales
    assert df["numero_historia"].iloc[0] == "001001"


from src.limpiar_datos import limpiar_datos


def test_consolidacion_y_limpieza():

    # Arrange: crear datos consolidados simulados
    datos = pd.DataFrame({
        "numero_historia": ["001001", "001002", "001002", "001003"],
        "edad": [35, 42, 42, None],
        "hospital_origen": [
            "Hospital 1",
            "Hospital 2",
            "Hospital 2",
            "Hospital 3"
        ]
    })

    # Act: ejecutar la limpieza
    df_limpio, df_incompletos, df_duplicados = limpiar_datos(datos)

    # Assert: comprobar los resultados
    assert len(df_limpio) == 2
    assert len(df_incompletos) == 1
    assert len(df_duplicados) == 1

    # Comprobar que se conservan los números de historia
    assert df_limpio["numero_historia"].tolist() == [
        "001001",
        "001002"
    ]


def test_limpieza_y_validacion():

    # Arrange: crear datos simulados
    datos = pd.DataFrame({
        "numero_historia": [
            "001001",
            "001002",
            "001003",
            "001004"
        ],
        "fecha": [
            "2026-01-10",
            "2026-01-11",
            "2026-01-12",
            "2026-01-13"
        ],
        "edad": [35, 42, 50, 29],
        "especialidad": [
            "Cirugia",
            "Urologia",
            "Cardiologia",
            "Traumatologia"
        ],
        "tecnica_anestesica": [
            "General",
            "Regional",
            "General",
            "Sedacion"
        ],
        "duracion_minutos": [90, 60, 120, 45],
        "hospital_origen": [
            "Hospital 1",
            "Hospital 2",
            "Hospital 3",
            "Hospital 1"
        ]
    })

    # Act: limpiar y validar
    df_limpio, _, _ = limpiar_datos(datos)

    df_validos, df_rechazados = validar_datos(df_limpio)

    # Assert: comprobar resultados
    assert len(df_limpio) == 4
    assert len(df_validos) == 3
    assert len(df_rechazados) == 1

    # Comprobar que Cardiologia fue rechazada
    assert (
        df_rechazados.iloc[0]["especialidad"]
        == "Cardiologia"
    )

    # Comprobar que se conserva el número de historia
    assert "001001" in df_validos["numero_historia"].tolist()


def test_pipeline_completo_hasta_validacion(tmp_path):

    # Arrange: crear tres archivos CSV temporales
    hospital_1 = pd.DataFrame({
        "numero_historia": ["001001", "001002"],
        "fecha": ["2026-01-10", "2026-01-11"],
        "edad": [35, 42],
        "especialidad": ["Cirugia", "Urologia"],
        "tecnica_anestesica": ["General", "Regional"],
        "duracion_minutos": [90, 60]
    })

    hospital_2 = pd.DataFrame({
        "numero_historia": ["002001", "002002"],
        "fecha": ["2026-01-12", "2026-01-13"],
        "edad": [50, 29],
        "especialidad": ["Cardiologia", "Traumatologia"],
        "tecnica_anestesica": ["General", "Sedacion"],
        "duracion_minutos": [120, 45]
    })

    hospital_3 = pd.DataFrame({
        "numero_historia": ["003001"],
        "fecha": ["2026-01-14"],
        "edad": [None],
        "especialidad": ["Cirugia"],
        "tecnica_anestesica": ["General"],
        "duracion_minutos": [80]
    })

    hospital_1.to_csv(tmp_path / "hospital_1.csv", index=False)
    hospital_2.to_csv(tmp_path / "hospital_2.csv", index=False)
    hospital_3.to_csv(tmp_path / "hospital_3.csv", index=False)

    archivos = {
        "hospital_1.csv": "Hospital 1",
        "hospital_2.csv": "Hospital 2",
        "hospital_3.csv": "Hospital 3"
    }

    # Act 1: consolidar
    df_consolidado = consolidar_datos(archivos, tmp_path)

    # Act 2: limpiar
    df_limpio, df_incompletos, df_duplicados = limpiar_datos(
        df_consolidado
    )

    # Act 3: validar
    df_validos, df_rechazados = validar_datos(df_limpio)

    # Assert: comprobar resultados del proceso
    assert len(df_consolidado) == 5

    assert len(df_limpio) == 4
    assert len(df_incompletos) == 1
    assert len(df_duplicados) == 0

    assert len(df_validos) == 3
    assert len(df_rechazados) == 1

    # Comprobar que el registro inválido fue rechazado
    assert (
        df_rechazados.iloc[0]["especialidad"]
        == "Cardiologia"
    )

    # Comprobar que no se perdieron los ceros iniciales
    assert "001001" in df_validos["numero_historia"].tolist()
