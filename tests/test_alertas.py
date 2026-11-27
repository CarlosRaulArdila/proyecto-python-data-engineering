
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import MagicMock

import pytest

from src import alertas
from src.alertas import (
    construir_mensaje,
    cuerpo_webhook,
    estado_de_alerta,
    notificar,
    validar_config_alertas,
)

RESUMEN = {
    "estado": "FALLIDO",
    "proyecto_id": "proyecto_x",
    "pipeline_id": "pipeline_x",
    "ambiente": "desarrollo",
    "orquestador": "manual",
    "version_pipeline": "9.9.9",
    "run_id": "abc-123",
    "id_ejecucion": 7,
    "duracion_segundos": 1.234,
    "metricas": {"registros_extraidos": 15, "registros_rechazados": 3},
    "mensaje_error": "limpiar: no existe el archivo",
    "advertencias": None,
}

EMAIL = {"tipo": "email", "destinatarios": ["a@x.com", "b@x.com"]}


@pytest.fixture
def smtp(monkeypatch):
    for nombre, valor in {
        "ETL_SMTP_HOST": "smtp.prueba.local",
        "ETL_SMTP_USUARIO": "etl@x.com",
        "ETL_SMTP_CLAVE": "secreta",
        "ETL_SMTP_PUERTO": "587",
    }.items():
        monkeypatch.setenv(nombre, valor)

    servidor = MagicMock()
    clase = MagicMock()
    clase.return_value.__enter__.return_value = servidor
    monkeypatch.setattr(alertas.smtplib, "SMTP", clase)
    return clase, servidor


def test_estado_de_alerta():

    assert estado_de_alerta("EXITOSO", "algo") == "ADVERTENCIA"
    assert estado_de_alerta("EXITOSO", None) == "EXITOSO"
    assert estado_de_alerta("FALLIDO", "algo") == "FALLIDO"


def test_construir_mensaje():

    asunto, cuerpo = construir_mensaje(RESUMEN)

    assert asunto == "[ETL] FALLIDO - pipeline_x (desarrollo)"
    assert "Run ID:        abc-123" in cuerpo
    assert "Extraídos:   15" in cuerpo
    assert "limpiar: no existe el archivo" in cuerpo
    assert "WHERE run_id = 'abc-123'" in cuerpo


def test_email_enviado_con_starttls(smtp):

    clase, servidor = smtp

    enviados = notificar(RESUMEN, {"notificar_en": ["FALLIDO"], "canales": [EMAIL]})

    assert enviados == ["email"]
    clase.assert_called_once_with("smtp.prueba.local", 587, timeout=alertas.TIEMPO_ESPERA)
    servidor.starttls.assert_called_once()
    servidor.login.assert_called_once_with("etl@x.com", "secreta")

    mensaje = servidor.send_message.call_args.args[0]
    assert mensaje["Subject"] == "[ETL] FALLIDO - pipeline_x (desarrollo)"
    assert mensaje["To"] == "a@x.com, b@x.com"
    assert mensaje["From"] == "etl@x.com"


def test_destinatarios_desde_variable(smtp, monkeypatch):

    _, servidor = smtp
    monkeypatch.setenv("ETL_ALERTA_DESTINATARIOS", "uno@x.com, dos@x.com")
    canal = {"tipo": "email", "destinatarios_env": "ETL_ALERTA_DESTINATARIOS"}

    notificar(RESUMEN, {"canales": [canal]})

    assert servidor.send_message.call_args.args[0]["To"] == "uno@x.com, dos@x.com"


def test_estado_no_alertable_no_envia(smtp):

    _, servidor = smtp

    exitoso = {**RESUMEN, "estado": "EXITOSO", "mensaje_error": None}

    assert notificar(exitoso, {"canales": [EMAIL]}) == []
    servidor.send_message.assert_not_called()


def test_advertencia_se_notifica(smtp):

    _, servidor = smtp
    con_advertencia = {**RESUMEN, "estado": "EXITOSO", "advertencias": "Umbral..."}

    assert notificar(con_advertencia, {"canales": [EMAIL]}) == ["email"]
    assert "[ETL] ADVERTENCIA" in servidor.send_message.call_args.args[0]["Subject"]


def test_canal_sin_variables_se_omite(monkeypatch, caplog):

    for nombre in ("ETL_SMTP_HOST", "ETL_SMTP_USUARIO", "ETL_SMTP_CLAVE"):
        monkeypatch.delenv(nombre, raising=False)

    assert notificar(RESUMEN, {"canales": [EMAIL]}) == []
    assert "Falta la variable de entorno ETL_SMTP_HOST" in caplog.text


def test_error_de_envio_no_rompe_el_pipeline(smtp, caplog):

    _, servidor = smtp
    servidor.login.side_effect = OSError("credenciales inválidas")

    assert notificar(RESUMEN, {"canales": [EMAIL]}) == []
    assert "No se pudo enviar la alerta por email" in caplog.text


def test_configuracion_invalida_no_rompe(caplog):

    assert notificar(RESUMEN, {"canales": [{"tipo": "sms"}]}) == []
    assert "Configuración de alertas inválida" in caplog.text


@pytest.mark.parametrize(
    ("config", "mensaje"),
    [
        ({"notificar_en": ["ROTO"], "canales": []}, "estados desconocidos"),
        ({"canales": [{"tipo": "sms"}]}, "tipo inválido"),
        ({"canales": [{"tipo": "email"}]}, "destinatarios"),
        ({"canales": [{"tipo": "webhook"}]}, "url_env"),
        ({"canales": [{"tipo": "webhook", "url_env": "X", "formato": "discord"}]}, "Formato"),
    ],
)
def test_validar_config(config, mensaje):

    with pytest.raises(ValueError, match=mensaje):
        validar_config_alertas(config)


def test_formatos_de_webhook():

    assert cuerpo_webhook("slack", "A", "B", {})["text"].startswith("*A*")
    teams = cuerpo_webhook("teams", "A", "B", {})
    assert teams["attachments"][0]["content"]["type"] == "AdaptiveCard"
    assert cuerpo_webhook("generico", "A", "B", {"x": 1}) == {
        "asunto": "A", "mensaje": "B", "ejecucion": {"x": 1}
    }


@pytest.fixture
def servidor_http():
    recibidos = []

    class Manejador(BaseHTTPRequestHandler):
        def do_POST(self):
            largo = int(self.headers["Content-Length"])
            recibidos.append(json.loads(self.rfile.read(largo)))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    servidor = HTTPServer(("127.0.0.1", 0), Manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_port}/hook", recibidos
    servidor.shutdown()


def test_webhook_real(servidor_http, monkeypatch):

    url, recibidos = servidor_http
    monkeypatch.setenv("URL_HOOK", url)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("http_proxy", raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    canal = {"tipo": "webhook", "formato": "generico", "url_env": "URL_HOOK"}

    assert notificar(RESUMEN, {"canales": [canal]}) == ["webhook"]
    assert recibidos[0]["asunto"] == "[ETL] FALLIDO - pipeline_x (desarrollo)"
    assert recibidos[0]["ejecucion"]["run_id"] == "abc-123"


def test_config_del_proyecto_es_valida():

    from src.configuracion import CONFIG

    configuracion = validar_config_alertas(CONFIG["alertas"])

    assert configuracion["canales"][0]["tipo"] == "email"
    assert "FALLIDO" in configuracion["notificar_en"]
