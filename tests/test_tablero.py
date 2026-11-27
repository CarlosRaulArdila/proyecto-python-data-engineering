
from datetime import date, datetime, timedelta

from src.tablero import DatosPipeline, generar_html, grafico_barras, insignia


def pipeline(estado="OK", **extra):
    hoy = date.today()
    datos = DatosPipeline(
        proyecto="proyecto_x",
        pipeline_id=f"p_{estado.lower()}",
        esquema="public",
        ruta_config="config/config.yaml",
        salud={
            "salud": estado,
            "ultima_ejecucion": datetime(2026, 11, 26, 6, 0),
            "horas_desde_ultimo_exito": 2.5,
            "ejecuciones_7d": 7,
            "fallidas_7d": 1,
            "version_pipeline": "2.1.0",
            "ultimo_error": None,
            "ultimas_advertencias": None,
        },
        calidad=[{"dia": hoy - timedelta(days=1), "exitosas": 1, "fallidas": 1,
                  "porcentaje_rechazo": 20.0}],
        ejecuciones=[{
            "id": 9, "fecha_inicio": datetime(2026, 11, 26, 6, 0), "estado_operativo": "EXITOSO",
            "orquestador": "airflow", "registros_extraidos": 15, "registros_rechazados": 3,
            "porcentaje_rechazo": 20.0, "operaciones_bd": 0, "archivos_procesados": 3,
            "duracion_segundos": 0.7,
        }],
    )
    for clave, valor in extra.items():
        setattr(datos, clave, valor)
    return datos


def test_insignia_lleva_icono_y_texto():

    resultado = insignia("FALLANDO")

    assert "fallando" in resultado and "✕" in resultado and "Fallando" in resultado


def test_html_completo_y_ordenado_por_urgencia():

    contenido = generar_html(
        [pipeline("OK"), pipeline("FALLANDO")], 14, datetime(2026, 11, 26, 7, 0)
    )

    assert contenido.startswith("<!DOCTYPE html>")
    assert "2 pipelines" in contenido
    assert contenido.index("p_fallando") < contenido.index("p_ok")
    assert "20.0 %" in contenido
    assert "http" not in contenido  # sin recursos externos


def test_escapa_textos_de_la_base():

    malicioso = pipeline("FALLANDO")
    malicioso.salud["ultimo_error"] = "<script>alert(1)</script>"

    contenido = generar_html([malicioso], 14, datetime.now())

    assert "<script>alert(1)</script>" not in contenido
    assert "&lt;script&gt;" in contenido


def test_pipeline_sin_vistas_o_sin_datos():

    sin_vistas = pipeline(error="Faltan las vistas", salud=None)
    sin_datos = pipeline(salud=None)

    assert sin_vistas.estado_salud == "SIN_VISTAS"
    assert sin_datos.estado_salud == "SIN_DATOS"

    contenido = generar_html([sin_vistas, sin_datos], 14, datetime.now())

    assert "Faltan las vistas" in contenido
    assert "todavía no tiene ejecuciones" in contenido


def test_eje_de_conteos_usa_marcas_enteras():

    filas = [{"dia": date(2026, 11, 26), "exitosas": 1, "fallidas": 0}]

    svg = grafico_barras(filas, [("exitosas", "s-ok", "Exitosas")], "Ejecuciones")

    marcas = [t.split(">")[1].split("<")[0] for t in svg.split('class="eje"')[1:4]]
    assert marcas == ["0", "1", "2"]
    assert "<title>2026-11-26 · Exitosas: 1</title>" in svg
