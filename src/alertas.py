"""
Alertas de ejecución por correo (SMTP) o webhook (Slack, Teams, genérico).

Configuración en config.yaml (sin secretos):

    alertas:
      # Estados que generan una alerta. ADVERTENCIA = EXITOSO con advertencias.
      notificar_en: ["FALLIDO", "PARCIAL", "ADVERTENCIA"]
      canales:
        - tipo: "email"
          destinatarios_env: "ETL_ALERTA_DESTINATARIOS"   # o destinatarios: [...]
        - tipo: "webhook"
          formato: "slack"                 # slack | teams | generico
          url_env: "ETL_ALERTA_WEBHOOK_URL"

Secretos en variables de entorno (o en .env, que no se versiona):

    ETL_SMTP_HOST, ETL_SMTP_PUERTO (587), ETL_SMTP_USUARIO, ETL_SMTP_CLAVE,
    ETL_SMTP_REMITENTE (por defecto, el usuario), ETL_ALERTA_DESTINATARIOS
    (separados por coma), ETL_ALERTA_WEBHOOK_URL

Principios:
- Una alerta que no se puede enviar NUNCA hace fallar el pipeline: se
  registra en el log y la ejecución conserva su estado real.
- Un canal sin sus variables de entorno se omite con un aviso.

Prueba de configuración (envía una alerta de ejemplo):

    python -m src.alertas --prueba
"""

import json
import logging
import os
import smtplib
import ssl
import sys
import urllib.request
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Sin importar src.configuracion aquí: configuracion valida la sección
# 'alertas' al cargarse y una importación mutua sería circular.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

ESTADOS_ALERTABLES = {"FALLIDO", "PARCIAL", "ADVERTENCIA", "EXITOSO"}
TIPOS_CANAL = {"email", "webhook"}
FORMATOS_WEBHOOK = {"slack", "teams", "generico"}
TIEMPO_ESPERA = 15  # segundos


class CanalNoConfigurado(RuntimeError):
    """Faltan variables de entorno para usar un canal."""


# ------------------------------------------------------------------
# Configuración
# ------------------------------------------------------------------


def validar_config_alertas(alertas: dict | None) -> dict:
    """Valida la sección `alertas` y devuelve la configuración normalizada."""

    if not alertas:
        return {}

    if not isinstance(alertas, dict):
        raise ValueError("La sección 'alertas' debe ser un diccionario.")

    notificar_en = alertas.get("notificar_en", ["FALLIDO", "PARCIAL", "ADVERTENCIA"])
    desconocidos = set(notificar_en) - ESTADOS_ALERTABLES

    if desconocidos:
        raise ValueError(
            f"alertas.notificar_en tiene estados desconocidos: {sorted(desconocidos)}. "
            f"Permitidos: {sorted(ESTADOS_ALERTABLES)}"
        )

    canales = alertas.get("canales") or []

    for indice, canal in enumerate(canales, start=1):
        tipo = canal.get("tipo") if isinstance(canal, dict) else None

        if tipo not in TIPOS_CANAL:
            raise ValueError(
                f"Canal de alerta #{indice} con tipo inválido: {tipo!r}. "
                f"Use: {sorted(TIPOS_CANAL)}"
            )

        if tipo == "email" and not (canal.get("destinatarios") or canal.get("destinatarios_env")):
            raise ValueError(
                f"El canal de alerta #{indice} (email) requiere 'destinatarios' "
                "o 'destinatarios_env'."
            )

        if tipo == "webhook":
            if canal.get("formato", "generico") not in FORMATOS_WEBHOOK:
                raise ValueError(
                    f"Formato de webhook inválido en el canal #{indice}. "
                    f"Use: {sorted(FORMATOS_WEBHOOK)}"
                )
            if not canal.get("url_env"):
                raise ValueError(
                    f"El canal de alerta #{indice} (webhook) requiere 'url_env' "
                    "(nombre de la variable de entorno con la URL)."
                )

    return {"notificar_en": list(notificar_en), "canales": canales}


def estado_de_alerta(estado: str, advertencias: str | None) -> str:
    """EXITOSO con advertencias se notifica como ADVERTENCIA."""

    return "ADVERTENCIA" if estado == "EXITOSO" and advertencias else estado


# ------------------------------------------------------------------
# Mensaje
# ------------------------------------------------------------------


def construir_mensaje(resumen: dict) -> tuple[str, str]:
    """Devuelve (asunto, cuerpo en texto) a partir del resumen de la ejecución."""

    estado = estado_de_alerta(resumen.get("estado", "?"), resumen.get("advertencias"))
    pipeline = resumen.get("pipeline_id", "?")
    ambiente = resumen.get("ambiente", "?")
    metricas = resumen.get("metricas", {})

    asunto = f"[ETL] {estado} - {pipeline} ({ambiente})"

    lineas = [
        f"Estado:        {estado}",
        f"Proyecto:      {resumen.get('proyecto_id', '?')}",
        f"Pipeline:      {pipeline}",
        f"Ambiente:      {ambiente}",
        f"Orquestador:   {resumen.get('orquestador', '?')}",
        f"Versión:       {resumen.get('version_pipeline', '?')}",
        f"ID auditoría:  {resumen.get('id_ejecucion', '-')}",
        f"Run ID:        {resumen.get('run_id', '-')}",
        f"Duración:      {resumen.get('duracion_segundos', 0):.2f} s",
        "",
        "Métricas:",
        f"  Extraídos:   {metricas.get('registros_extraidos', 0)}",
        f"  Limpios:     {metricas.get('registros_limpios', 0)}",
        f"  Rechazados:  {metricas.get('registros_rechazados', 0)}",
        f"  Operaciones: {metricas.get('operaciones_bd', 0)}",
    ]

    if resumen.get("mensaje_error"):
        lineas += ["", "Error:", f"  {resumen['mensaje_error']}"]

    if resumen.get("advertencias"):
        lineas += ["", "Advertencias:", f"  {resumen['advertencias']}"]

    if resumen.get("archivo_log"):
        lineas += ["", f"Log: {resumen['archivo_log']}"]

    lineas += [
        "",
        "Detalle en la base de datos:",
        f"  SELECT * FROM etl_auditoria WHERE run_id = '{resumen.get('run_id', '')}';",
        f"  SELECT tipo, motivo, count(*) FROM etl_rechazos "
        f"WHERE run_id = '{resumen.get('run_id', '')}' GROUP BY 1, 2;",
    ]

    return asunto, "\n".join(lineas)


# ------------------------------------------------------------------
# Canales
# ------------------------------------------------------------------


def _variable(nombre: str) -> str:
    valor = os.getenv(nombre)

    if not valor:
        raise CanalNoConfigurado(f"Falta la variable de entorno {nombre}")

    return valor


def destinatarios_de(canal: dict) -> list[str]:
    if canal.get("destinatarios"):
        return list(canal["destinatarios"])

    valor = _variable(canal["destinatarios_env"])
    return [d.strip() for d in valor.split(",") if d.strip()]


def enviar_email(canal: dict, asunto: str, cuerpo: str) -> None:
    host = _variable("ETL_SMTP_HOST")
    usuario = _variable("ETL_SMTP_USUARIO")
    clave = _variable("ETL_SMTP_CLAVE")
    puerto = int(os.getenv("ETL_SMTP_PUERTO", "587"))
    remitente = os.getenv("ETL_SMTP_REMITENTE") or usuario
    destinatarios = destinatarios_de(canal)

    if not destinatarios:
        raise CanalNoConfigurado("No hay destinatarios para el canal de correo")

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = remitente
    mensaje["To"] = ", ".join(destinatarios)
    mensaje.set_content(cuerpo)

    contexto_tls = ssl.create_default_context()

    if puerto == 465:
        with smtplib.SMTP_SSL(host, puerto, context=contexto_tls, timeout=TIEMPO_ESPERA) as smtp:
            smtp.login(usuario, clave)
            smtp.send_message(mensaje)
    else:
        with smtplib.SMTP(host, puerto, timeout=TIEMPO_ESPERA) as smtp:
            smtp.starttls(context=contexto_tls)
            smtp.login(usuario, clave)
            smtp.send_message(mensaje)


def cuerpo_webhook(formato: str, asunto: str, cuerpo: str, resumen: dict) -> dict:
    if formato == "slack":
        return {"text": f"*{asunto}*\n```{cuerpo}```"}

    if formato == "teams":
        # Webhooks de flujos de trabajo (Workflows) de Microsoft Teams
        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {"type": "TextBlock", "text": asunto, "weight": "Bolder",
                             "wrap": True},
                            {"type": "TextBlock", "text": cuerpo, "wrap": True,
                             "fontType": "Monospace"},
                        ],
                    },
                }
            ],
        }

    return {"asunto": asunto, "mensaje": cuerpo, "ejecucion": resumen}


def enviar_webhook(canal: dict, asunto: str, cuerpo: str, resumen: dict) -> None:
    url = _variable(canal["url_env"])
    datos = cuerpo_webhook(canal.get("formato", "generico"), asunto, cuerpo, resumen)

    solicitud = urllib.request.Request(
        url,
        data=json.dumps(datos, ensure_ascii=False, default=str).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(solicitud, timeout=TIEMPO_ESPERA) as respuesta:
        if respuesta.status >= 300:
            raise RuntimeError(f"El webhook respondió con estado HTTP {respuesta.status}")


# ------------------------------------------------------------------
# Punto de entrada
# ------------------------------------------------------------------


def notificar(resumen: dict, config_alertas: dict | None = None) -> list[str]:
    """
    Envía la alerta por los canales configurados si el estado lo requiere.
    Devuelve los canales a los que se envió. Nunca lanza excepciones.
    """

    try:
        if config_alertas is None:
            from src.configuracion import CONFIG

            config_alertas = CONFIG.get("alertas")

        alertas = validar_config_alertas(config_alertas)
    except Exception:
        logger.exception("Configuración de alertas inválida: no se envían alertas.")
        return []

    if not alertas or not alertas["canales"]:
        return []

    estado = estado_de_alerta(resumen.get("estado", ""), resumen.get("advertencias"))

    if estado not in alertas["notificar_en"]:
        return []

    asunto, cuerpo = construir_mensaje(resumen)
    enviados = []

    for canal in alertas["canales"]:
        tipo = canal["tipo"]

        try:
            if tipo == "email":
                enviar_email(canal, asunto, cuerpo)
            else:
                enviar_webhook(canal, asunto, cuerpo, resumen)

            enviados.append(tipo)
            logger.info("Alerta enviada por %s: %s", tipo, asunto)

        except CanalNoConfigurado as error:
            logger.warning("Canal de alerta '%s' omitido: %s", tipo, error)

        except Exception:
            logger.exception("No se pudo enviar la alerta por %s", tipo)

    return enviados


def main(argumentos: list[str]) -> int:
    from src.configuracion import CONFIG
    from src.registro_logs import configurar_logging

    configurar_logging()

    if "--prueba" not in argumentos:
        print("Uso: python -m src.alertas --prueba")
        return 2

    alertas = validar_config_alertas(CONFIG.get("alertas"))

    if not alertas.get("canales"):
        logger.error("No hay canales de alerta configurados en config.yaml (alertas.canales).")
        return 1

    resumen = {
        "estado": "FALLIDO",
        "proyecto_id": CONFIG["proyecto"]["nombre"],
        "pipeline_id": CONFIG["pipeline"]["id"],
        "ambiente": CONFIG["proyecto"].get("entorno", "desarrollo"),
        "orquestador": "prueba",
        "version_pipeline": CONFIG["proyecto"].get("version", "?"),
        "run_id": "00000000-0000-0000-0000-000000000000",
        "duracion_segundos": 0.0,
        "metricas": {},
        "mensaje_error": "ALERTA DE PRUEBA: la configuración de alertas funciona.",
    }

    enviados = notificar(resumen, {**alertas, "notificar_en": ["FALLIDO"]})

    if enviados:
        logger.info("Prueba completada. Canales: %s", ", ".join(enviados))
        return 0

    logger.error("No se envió ninguna alerta. Revise los avisos anteriores.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
