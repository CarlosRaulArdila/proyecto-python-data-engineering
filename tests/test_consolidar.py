
import pandas as pd
import pytest

from src.consolidar_datos import consolidar_datos, detectar_archivos_no_configurados
from src.esquema import construir_esquema

ESQUEMA = construir_esquema({
    "columnas": [
        {"nombre": "numero_historia", "tipo": "texto"},
        {"nombre": "edad", "tipo": "entero"},
        {"nombre": "hospital_origen", "tipo": "texto", "derivada": True},
    ]
})


def test_detectar_archivos_no_configurados(tmp_path):

    for nombre in ("hospital_1.csv", "hospital_2.csv", "nuevos_registros.csv"):
        pd.DataFrame({"a": [1]}).to_csv(tmp_path / nombre, index=False)

    (tmp_path / "notas.txt").write_text("no es csv")

    resultado = detectar_archivos_no_configurados(
        tmp_path, {"hospital_1.csv", "hospital_2.csv"}
    )

    assert resultado == ["nuevos_registros.csv"]


def test_sin_archivos_extra(tmp_path):

    pd.DataFrame({"a": [1]}).to_csv(tmp_path / "hospital_1.csv", index=False)

    assert detectar_archivos_no_configurados(tmp_path, {"hospital_1.csv"}) == []


def test_consolidar_con_esquema_descarta_columnas_extra(tmp_path):

    pd.DataFrame({
        "edad": [30],
        "numero_historia": ["000123"],
        "hospital_origen": ["valor de la fuente"],
        "columna_extra": ["x"],
    }).to_csv(tmp_path / "h1.csv", index=False)

    df = consolidar_datos({"h1.csv": "Hospital 1"}, tmp_path, ESQUEMA)

    assert list(df.columns) == ["numero_historia", "edad", "hospital_origen"]
    assert df.loc[0, "numero_historia"] == "000123"
    # hospital_origen es derivada: manda la configuración, no el archivo
    assert df.loc[0, "hospital_origen"] == "Hospital 1"


def test_consolidar_con_esquema_falla_si_falta_columna(tmp_path):

    pd.DataFrame({"numero_historia": ["1"]}).to_csv(tmp_path / "h1.csv", index=False)

    with pytest.raises(ValueError, match=r"h1\.csv.*edad"):
        consolidar_datos({"h1.csv": "Hospital 1"}, tmp_path, ESQUEMA)
