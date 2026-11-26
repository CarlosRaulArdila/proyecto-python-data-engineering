
import pandas as pd

from src.consolidar_datos import detectar_archivos_no_configurados


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
