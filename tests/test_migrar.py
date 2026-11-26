
import pytest

from src.migrar import DIRECTORIO_MIGRACIONES, listar_migraciones


def test_migraciones_del_proyecto_ordenadas_y_consecutivas():

    migraciones = listar_migraciones(DIRECTORIO_MIGRACIONES)
    versiones = [m.version for m in migraciones]

    assert versiones == list(range(1, len(versiones) + 1))
    assert migraciones[0].ruta.name.startswith("V001__")


def test_orden_numerico_no_alfabetico(tmp_path):

    (tmp_path / "V10__diez.sql").write_text("SELECT 10;")
    (tmp_path / "V2__dos.sql").write_text("SELECT 2;")

    assert [m.version for m in listar_migraciones(tmp_path)] == [2, 10]


def test_nombre_invalido(tmp_path):

    (tmp_path / "crear_tabla.sql").write_text("SELECT 1;")

    with pytest.raises(ValueError, match="Nombre de migración inválido"):
        listar_migraciones(tmp_path)


def test_version_duplicada(tmp_path):

    (tmp_path / "V1__a.sql").write_text("SELECT 1;")
    (tmp_path / "V001__b.sql").write_text("SELECT 1;")

    with pytest.raises(ValueError, match="duplicadas"):
        listar_migraciones(tmp_path)


def test_checksum_cambia_si_cambia_el_archivo(tmp_path):

    ruta = tmp_path / "V1__a.sql"
    ruta.write_text("SELECT 1;")
    antes = listar_migraciones(tmp_path)[0].checksum

    ruta.write_text("SELECT 2;")
    despues = listar_migraciones(tmp_path)[0].checksum

    assert antes != despues


def test_checksum_ignora_finales_de_linea(tmp_path):

    lf = tmp_path / "lf"
    crlf = tmp_path / "crlf"
    lf.mkdir()
    crlf.mkdir()

    (lf / "V1__a.sql").write_bytes(b"SELECT 1;\nSELECT 2;\n")
    (crlf / "V1__a.sql").write_bytes(b"SELECT 1;\r\nSELECT 2;\r\n")

    assert listar_migraciones(lf)[0].checksum == listar_migraciones(crlf)[0].checksum


def test_marcador_de_esquema(tmp_path, monkeypatch):

    from src import migrar

    monkeypatch.setattr(migrar, "ESQUEMA_BD", "ventas")
    (tmp_path / "V1__a.sql").write_text("CREATE TABLE {{esquema}}.t (id int);")

    migracion = listar_migraciones(tmp_path)[0]

    assert migracion.sql == "CREATE TABLE ventas.t (id int);"


def test_directorio_inexistente(tmp_path):

    with pytest.raises(FileNotFoundError, match="migraciones"):
        listar_migraciones(tmp_path / "no_existe")
