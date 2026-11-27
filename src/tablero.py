"""
Tablero de operación: una página HTML autocontenida con el estado de todos
los pipelines del proyecto.

Lee las vistas de operación (migración "vistas_de_operacion") de cada
esquema configurado en config/config.yaml y pipelines/*/config.yaml:

    vw_etl_salud, vw_etl_calidad_diaria, vw_etl_ejecuciones,
    vw_etl_rechazos_resumen, vw_etl_linaje

No usa librerías ni recursos externos (sin CDN): el archivo se puede abrir
sin conexión, enviar por correo o publicar tal cual.

Uso:
    python -m src.tablero                       # reportes/tablero_operacion.html
    python -m src.tablero --salida ruta.html
    python -m src.tablero --dias 30

La salida por defecto puede cambiarse con la variable ETL_TABLERO_SALIDA.
"""

import argparse
import html
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from src.configuracion import BASE_DIR, cargar_configuracion
from src.sql_utils import validar_identificador

logger = logging.getLogger(__name__)

SALIDA_POR_DEFECTO = Path(
    os.getenv("ETL_TABLERO_SALIDA") or BASE_DIR / "reportes" / "tablero_operacion.html"
)

# Estado -> (clase CSS, ícono, texto). El color nunca va solo: ícono + texto.
SALUD = {
    "OK": ("ok", "✓", "OK"),
    "ADVERTENCIA": ("advertencia", "!", "Advertencia"),
    "ATRASADO": ("atrasado", "⏱", "Atrasado"),
    "FALLANDO": ("fallando", "✕", "Fallando"),
    "EN_PROCESO": ("proceso", "…", "En proceso"),
    "SIN_DATOS": ("sin-datos", "–", "Sin ejecuciones"),
    "SIN_VISTAS": ("sin-datos", "?", "Faltan vistas"),
}


@dataclass
class DatosPipeline:
    proyecto: str
    pipeline_id: str
    esquema: str
    ruta_config: str
    salud: dict | None = None
    calidad: list[dict] = field(default_factory=list)
    ejecuciones: list[dict] = field(default_factory=list)
    rechazos: list[dict] = field(default_factory=list)
    linaje: list[dict] = field(default_factory=list)
    error: str | None = None

    @property
    def estado_salud(self) -> str:
        if self.error:
            return "SIN_VISTAS"
        if not self.salud:
            return "SIN_DATOS"
        return self.salud["salud"]


# ------------------------------------------------------------------
# Datos
# ------------------------------------------------------------------


def descubrir_proyectos(base: Path = BASE_DIR) -> list[tuple[str, dict]]:
    """[(ruta_relativa, config)] del pipeline principal y de pipelines/*/."""

    rutas = [base / "config" / "config.yaml"]
    rutas += [
        r for r in sorted((base / "pipelines").glob("*/config.yaml"))
        if not r.parent.name.startswith("_")
    ]

    return [
        (r.relative_to(base).as_posix(), cargar_configuracion(r)) for r in rutas if r.exists()
    ]


def _filas(conexion, sql: str, parametros: dict) -> list[dict]:
    return [dict(fila._mapping) for fila in conexion.execute(text(sql), parametros)]


def obtener_datos(conexion, ruta_config: str, config: dict, dias: int) -> DatosPipeline:
    esquema = validar_identificador(config["base_datos"]["esquema"], "Esquema")
    pipeline_id = config["pipeline"]["id"]
    datos = DatosPipeline(
        proyecto=config["proyecto"]["nombre"],
        pipeline_id=pipeline_id,
        esquema=esquema,
        ruta_config=ruta_config,
    )
    p = {"pipeline_id": pipeline_id, "desde": date.today() - timedelta(days=dias - 1)}

    try:
        salud = _filas(
            conexion, f"SELECT * FROM {esquema}.vw_etl_salud WHERE pipeline_id = :pipeline_id", p
        )
        datos.salud = salud[0] if salud else None
        datos.calidad = _filas(
            conexion,
            f"SELECT * FROM {esquema}.vw_etl_calidad_diaria "
            "WHERE pipeline_id = :pipeline_id AND dia >= :desde ORDER BY dia",
            p,
        )
        datos.ejecuciones = _filas(
            conexion,
            f"SELECT * FROM {esquema}.vw_etl_ejecuciones "
            "WHERE pipeline_id = :pipeline_id ORDER BY fecha_inicio DESC LIMIT 10",
            p,
        )
        datos.rechazos = _filas(
            conexion,
            f"SELECT * FROM {esquema}.vw_etl_rechazos_resumen "
            "WHERE pipeline_id = :pipeline_id AND ultima_vez >= :desde "
            "ORDER BY registros DESC, ultima_vez DESC LIMIT 5",
            p,
        )
        datos.linaje = _filas(
            conexion,
            f"SELECT * FROM {esquema}.vw_etl_linaje WHERE pipeline_id = :pipeline_id "
            f"AND run_id = (SELECT run_id FROM {esquema}.vw_etl_linaje "
            "WHERE pipeline_id = :pipeline_id ORDER BY fecha_inicio DESC LIMIT 1) "
            "ORDER BY nombre_archivo",
            p,
        )
    except Exception as error:  # noqa: BLE001 - se muestra en el tablero
        conexion.rollback()
        datos.error = (
            f"No se pudieron leer las vistas de {esquema}: aplique las migraciones "
            f"(python -m src.migrar). Detalle: {str(error).splitlines()[0]}"
        )
        logger.warning(datos.error)

    return datos


# ------------------------------------------------------------------
# Presentación
# ------------------------------------------------------------------


def _e(valor) -> str:
    return html.escape("" if valor is None else str(valor))


def _fecha(valor) -> str:
    if isinstance(valor, datetime):
        return valor.astimezone().strftime("%Y-%m-%d %H:%M")
    return _e(valor)


def _numero(valor, decimales: int = 0) -> str:
    if valor is None:
        return "–"
    return f"{float(valor):,.{decimales}f}".replace(",", " ")


def insignia(estado: str) -> str:
    clase, icono, texto = SALUD.get(estado, SALUD["SIN_DATOS"])
    return (
        f'<span class="insignia {clase}"><span aria-hidden="true">{icono}</span> '
        f"{_e(texto)}</span>"
    )


def _dias_completos(calidad: list[dict], dias: int) -> list[dict]:
    """Rellena con ceros los días sin ejecuciones para que el eje sea continuo."""

    por_dia = {fila["dia"]: fila for fila in calidad}
    hoy = date.today()

    return [
        por_dia.get(hoy - timedelta(days=d), {"dia": hoy - timedelta(days=d)})
        for d in range(dias - 1, -1, -1)
    ]


def grafico_barras(
    filas: list[dict],
    segmentos: list[tuple[str, str, str]],
    titulo: str,
    formato=lambda v: _numero(v),
    maximo_fijo: float | None = None,
) -> str:
    """
    Barras (apiladas si hay varios segmentos) en SVG, con tooltip por barra.
    segmentos: [(clave, clase_css, etiqueta)]
    """

    ancho, alto, margen_izq, margen_inf, margen_sup = 560, 150, 34, 22, 8
    area_alto = alto - margen_inf - margen_sup
    n = max(len(filas), 1)
    paso = (ancho - margen_izq) / n
    barra = max(min(paso * 0.6, 22), 3)

    totales = [sum(float(f.get(c) or 0) for c, _, _ in segmentos) for f in filas]

    if maximo_fijo:
        maximo = maximo_fijo
    else:
        # Conteos: máximo par (mínimo 2) para que la marca del medio sea entera
        maximo = max(math.ceil(max(totales + [1])), 2)
        maximo += maximo % 2

    partes = [
        f'<svg viewBox="0 0 {ancho} {alto}" role="img" aria-label="{_e(titulo)}" '
        'class="grafico">'
    ]

    # Rejilla recesiva: 0, mitad y máximo
    for fraccion in (0, 0.5, 1):
        y = margen_sup + area_alto * (1 - fraccion)
        clase = "base" if fraccion == 0 else "rejilla"
        partes.append(
            f'<line class="{clase}" x1="{margen_izq}" x2="{ancho}" y1="{y:.1f}" y2="{y:.1f}"/>'
        )
        partes.append(
            f'<text class="eje" x="{margen_izq - 6}" y="{y + 4:.1f}" text-anchor="end">'
            f"{formato(maximo * fraccion)}</text>"
        )

    for i, fila in enumerate(filas):
        x = margen_izq + paso * i + (paso - barra) / 2
        base = margen_sup + area_alto
        detalle = [f"{fila['dia']}"]

        for j, (clave, clase, etiqueta) in enumerate(segmentos):
            valor = float(fila.get(clave) or 0)
            detalle.append(f"{etiqueta}: {formato(valor)}")
            if valor <= 0:
                continue
            h = area_alto * valor / maximo
            separacion = 2 if j > 0 else 0  # espacio de 2 px entre segmentos
            y = base - h
            redondeo = 4 if j == len(segmentos) - 1 or len(segmentos) == 1 else 0
            partes.append(
                f'<rect class="{clase}" x="{x:.1f}" y="{y:.1f}" width="{barra:.1f}" '
                f'height="{max(h - separacion, 1):.1f}" rx="{redondeo}"/>'
            )
            base = y

        # Zona sensible más grande que la barra, con el tooltip
        partes.append(
            f'<rect class="zona" x="{margen_izq + paso * i:.1f}" y="{margen_sup}" '
            f'width="{paso:.1f}" height="{area_alto}"><title>{_e(" · ".join(detalle))}'
            "</title></rect>"
        )

        if i == 0 or i == n - 1 or n <= 7:
            partes.append(
                f'<text class="eje" x="{x + barra / 2:.1f}" y="{alto - 6}" '
                f'text-anchor="middle">{_e(str(fila["dia"])[5:])}</text>'
            )

    partes.append("</svg>")

    leyenda = ""
    if len(segmentos) > 1:
        leyenda = '<div class="leyenda">' + "".join(
            f'<span><i class="muestra {clase}"></i>{_e(etiqueta)}</span>'
            for _, clase, etiqueta in segmentos
        ) + "</div>"

    return f'<figure><figcaption>{_e(titulo)}</figcaption>{leyenda}{"".join(partes)}</figure>'


def tarjeta_pipeline(datos: DatosPipeline, dias: int) -> str:
    estado = datos.estado_salud
    clase = SALUD.get(estado, SALUD["SIN_DATOS"])[0]
    s = datos.salud or {}

    encabezado = (
        f'<header><div><h2>{_e(datos.pipeline_id)}</h2>'
        f'<p class="secundario">{_e(datos.proyecto)} · esquema <code>{_e(datos.esquema)}</code>'
        f" · <code>{_e(datos.ruta_config)}</code></p></div>{insignia(estado)}</header>"
    )

    if datos.error:
        return f'<section class="tarjeta {clase}">{encabezado}<p>{_e(datos.error)}</p></section>'

    if not datos.salud:
        return (
            f'<section class="tarjeta {clase}">{encabezado}'
            "<p>Este pipeline todavía no tiene ejecuciones registradas.</p></section>"
        )

    # Rechazo de la última ejecución que procesó registros (una ejecución
    # fallida o sin archivos nuevos no tiene porcentaje)
    ultima = next(
        (e for e in datos.ejecuciones if e.get("porcentaje_rechazo") is not None), {}
    )
    indicadores = [
        ("Última ejecución", _fecha(s.get("ultima_ejecucion"))),
        ("Último éxito", f"hace {_numero(s.get('horas_desde_ultimo_exito'), 1)} h"
         if s.get("horas_desde_ultimo_exito") is not None else "nunca"),
        ("Ejecuciones (7 días)", _numero(s.get("ejecuciones_7d"))),
        ("Fallidas (7 días)", _numero(s.get("fallidas_7d"))),
        ("Último % de rechazo", f"{_numero(ultima.get('porcentaje_rechazo'), 1)} %"
         if ultima.get("porcentaje_rechazo") is not None else "–"),
        ("Versión", _e(s.get("version_pipeline"))),
    ]
    kpis = '<div class="kpis">' + "".join(
        f'<div><span class="secundario">{_e(n)}</span><strong>{v}</strong></div>'
        for n, v in indicadores
    ) + "</div>"

    aviso = ""
    if s.get("ultimo_error"):
        aviso = f'<p class="aviso critico"><strong>Último error:</strong> {_e(s["ultimo_error"])}</p>'
    elif s.get("ultimas_advertencias"):
        aviso = (
            f'<p class="aviso advertencia"><strong>Advertencias:</strong> '
            f'{_e(s["ultimas_advertencias"])}</p>'
        )

    serie = _dias_completos(datos.calidad, dias)
    graficos = '<div class="graficos">' + grafico_barras(
        serie,
        [("exitosas", "s-ok", "Exitosas"), ("fallidas", "s-falla", "Fallidas")],
        f"Ejecuciones por día (últimos {dias} días)",
    ) + grafico_barras(
        serie,
        [("porcentaje_rechazo", "s-serie", "% de rechazo")],
        f"% de registros rechazados por día (últimos {dias} días)",
        formato=lambda v: f"{v:.0f}%",
        maximo_fijo=max([float(f.get("porcentaje_rechazo") or 0) for f in serie] + [10]),
    ) + "</div>"

    filas_ejecuciones = "".join(
        "<tr>"
        f"<td>{_e(e['id'])}</td><td>{_fecha(e['fecha_inicio'])}</td>"
        f"<td>{insignia({'EXITOSO': 'OK', 'ADVERTENCIA': 'ADVERTENCIA', 'EN_PROCESO': 'EN_PROCESO'}.get(e['estado_operativo'], 'FALLANDO'))}</td>"  # noqa: E501
        f"<td>{_e(e['orquestador'])}</td>"
        f"<td class='num'>{_numero(e['registros_extraidos'])}</td>"
        f"<td class='num'>{_numero(e['registros_rechazados'])}</td>"
        f"<td class='num'>{_numero(e['porcentaje_rechazo'], 1)}</td>"
        f"<td class='num'>{_numero(e['operaciones_bd'])}</td>"
        f"<td class='num'>{_numero(e['archivos_procesados'])}</td>"
        f"<td class='num'>{_numero(e['duracion_segundos'], 2)}</td>"
        "</tr>"
        for e in datos.ejecuciones
    )
    tabla_ejecuciones = (
        "<h3>Últimas ejecuciones</h3><div class='tabla'><table><thead><tr>"
        "<th>ID</th><th>Inicio</th><th>Estado</th><th>Orquestador</th>"
        "<th class='num'>Extraídos</th><th class='num'>Rechazados</th>"
        "<th class='num'>% rechazo</th><th class='num'>Operaciones</th>"
        "<th class='num'>Archivos</th><th class='num'>Duración (s)</th>"
        f"</tr></thead><tbody>{filas_ejecuciones}</tbody></table></div>"
    )

    if datos.rechazos:
        filas_rechazos = "".join(
            f"<tr><td>{_e(r['tipo'])}</td><td>{_e(r['motivo'])}</td><td>{_e(r['fuente'])}</td>"
            f"<td class='num'>{_numero(r['registros'])}</td>"
            f"<td class='num'>{_numero(r['ejecuciones'])}</td></tr>"
            for r in datos.rechazos
        )
        tabla_rechazos = (
            f"<h3>Motivos de rechazo más frecuentes ({dias} días)</h3><div class='tabla'><table>"
            "<thead><tr><th>Tipo</th><th>Motivo</th><th>Fuente</th>"
            "<th class='num'>Registros</th><th class='num'>Ejecuciones</th></tr></thead>"
            f"<tbody>{filas_rechazos}</tbody></table></div>"
        )
    else:
        tabla_rechazos = f"<h3>Motivos de rechazo</h3><p class='secundario'>Sin rechazos en {dias} días.</p>"

    if datos.linaje:
        filas_linaje = "".join(
            f"<tr><td>{_e(f['fuente'])}</td><td><code>{_e(f['nombre_archivo'])}</code></td>"
            f"<td class='num'>{_numero(f['registros'])}</td>"
            f"<td><code>{_e(str(f['hash_sha256'])[:12])}</code></td></tr>"
            for f in datos.linaje
        )
        tabla_linaje = (
            f"<h3>Archivos de la última carga (ejecución {_e(datos.linaje[0]['id_ejecucion'])})</h3>"
            "<div class='tabla'><table><thead><tr><th>Fuente</th><th>Archivo</th>"
            "<th class='num'>Registros</th><th>Huella</th></tr></thead>"
            f"<tbody>{filas_linaje}</tbody></table></div>"
        )
    else:
        tabla_linaje = ""

    return (
        f'<section class="tarjeta {clase}">{encabezado}{kpis}{aviso}{graficos}'
        f"{tabla_ejecuciones}{tabla_rechazos}{tabla_linaje}</section>"
    )


ESTILOS = """
:root{--superficie:#ffffff;--fondo:#f6f6f4;--texto:#191919;--secundario:#666666;
--rejilla:#e7e7e7;--base:#c2c2c2;--borde:rgba(11,11,11,.10);
--ok:#0aac23;--advertencia:#fbb315;--serio:#f18a59;--critico:#dc3c3d;--serie:#257de0;
--ok-texto:#006c10;--critico-texto:#b42324}
@media (prefers-color-scheme:dark){:root{--superficie:#191919;--fondo:#0f0f0f;--texto:#efefef;
--secundario:#9c9c9c;--rejilla:#303030;--base:#474747;--borde:rgba(255,255,255,.10);
--serie:#338ced;--ok-texto:#53c556;--critico-texto:#f08a8b}}
*{box-sizing:border-box}
body{margin:0;background:var(--fondo);color:var(--texto);
font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:0}h3{font-size:14px;margin:22px 0 8px}
.secundario{color:var(--secundario);margin:0}
code{font:12px ui-monospace,SFMono-Regular,Consolas,monospace}
.resumen{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 22px}
.resumen div{background:var(--superficie);border:1px solid var(--borde);border-radius:10px;
padding:10px 14px;display:flex;gap:10px;align-items:center}
.tarjeta{background:var(--superficie);border:1px solid var(--borde);border-left:4px solid var(--base);
border-radius:12px;padding:18px 20px;margin-bottom:22px}
.tarjeta.ok{border-left-color:var(--ok)}.tarjeta.advertencia{border-left-color:var(--advertencia)}
.tarjeta.atrasado{border-left-color:var(--serio)}.tarjeta.fallando{border-left-color:var(--critico)}
.tarjeta header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.insignia{display:inline-flex;gap:4px;align-items:center;border-radius:999px;padding:2px 10px;
font-weight:600;font-size:12px;white-space:nowrap;border:1px solid var(--borde)}
.insignia span{font-weight:700}
.insignia.ok{background:color-mix(in srgb,var(--ok) 16%,transparent);color:var(--ok-texto)}
.insignia.advertencia{background:color-mix(in srgb,var(--advertencia) 24%,transparent)}
.insignia.atrasado{background:color-mix(in srgb,var(--serio) 24%,transparent)}
.insignia.fallando{background:color-mix(in srgb,var(--critico) 16%,transparent);color:var(--critico-texto)}
.insignia.sin-datos,.insignia.proceso{color:var(--secundario)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}
.kpis div{display:flex;flex-direction:column;border-top:1px solid var(--rejilla);padding-top:8px}
.kpis strong{font-size:18px;font-variant-numeric:tabular-nums}
.aviso{border-radius:8px;padding:8px 12px;margin:8px 0;border:1px solid var(--borde)}
.aviso.critico{background:color-mix(in srgb,var(--critico) 10%,transparent)}
.aviso.advertencia{background:color-mix(in srgb,var(--advertencia) 14%,transparent)}
.graficos{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}
figure{margin:0}figcaption{font-weight:600;margin-bottom:4px}
.grafico{width:100%;height:auto;display:block}
.grafico text.eje{fill:var(--secundario);font-size:10px}
.grafico line.rejilla{stroke:var(--rejilla);stroke-width:1}
.grafico line.base{stroke:var(--base);stroke-width:1}
.grafico .s-ok{fill:var(--ok)}.grafico .s-falla{fill:var(--critico)}.grafico .s-serie{fill:var(--serie)}
.grafico .zona{fill:transparent}.grafico .zona:hover{fill:var(--rejilla);fill-opacity:.35}
.leyenda{display:flex;gap:14px;font-size:12px;color:var(--secundario);margin-bottom:2px}
.leyenda span{display:inline-flex;gap:6px;align-items:center}
.muestra{width:10px;height:10px;border-radius:2px;display:inline-block}
.muestra.s-ok{background:var(--ok)}.muestra.s-falla{background:var(--critico)}
.tabla{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:6px 8px;border-bottom:1px solid var(--rejilla);text-align:left;vertical-align:top}
th{color:var(--secundario);font-weight:600}
.num{text-align:right;font-variant-numeric:tabular-nums}
footer{color:var(--secundario);font-size:12px;margin-top:30px}
"""


def generar_html(pipelines: list[DatosPipeline], dias: int, generado: datetime) -> str:
    conteo: dict[str, int] = {}
    for p in pipelines:
        conteo[p.estado_salud] = conteo.get(p.estado_salud, 0) + 1

    orden = ["FALLANDO", "ATRASADO", "ADVERTENCIA", "EN_PROCESO", "OK", "SIN_DATOS", "SIN_VISTAS"]
    resumen = '<div class="resumen">' + "".join(
        f"<div>{insignia(estado)}<strong>{conteo[estado]}</strong></div>"
        for estado in orden if estado in conteo
    ) + "</div>"

    # Primero lo que necesita atención
    pipelines = sorted(pipelines, key=lambda p: (orden.index(p.estado_salud), p.pipeline_id))
    tarjetas = "".join(tarjeta_pipeline(p, dias) for p in pipelines)

    return (
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Tablero de operación ETL</title>"
        f"<style>{ESTILOS}</style></head><body><main>"
        "<h1>Tablero de operación ETL</h1>"
        f"<p class='secundario'>{len(pipelines)} pipelines · generado el "
        f"{generado.strftime('%Y-%m-%d %H:%M')} · ventana de {dias} días · "
        "pase el cursor sobre las barras para ver el detalle</p>"
        f"{resumen}{tarjetas}"
        "<footer>Fuente: vistas vw_etl_* de cada esquema. Salud: FALLANDO = la última "
        "ejecución falló; ATRASADO = más de 26 h sin una ejecución exitosa; ADVERTENCIA = "
        "la última ejecución superó un umbral de calidad en modo advertir.</footer>"
        "</main></body></html>"
    )


def generar_tablero(salida: Path = SALIDA_POR_DEFECTO, dias: int = 14) -> Path:
    from src.conexion_db import obtener_engine

    proyectos = descubrir_proyectos()

    with obtener_engine().connect() as conexion:
        datos = [obtener_datos(conexion, ruta, config, dias) for ruta, config in proyectos]

    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(generar_html(datos, dias, datetime.now()), encoding="utf-8")

    logger.info(
        "Tablero generado: %s | Pipelines: %s",
        salida,
        ", ".join(f"{d.pipeline_id}={d.estado_salud}" for d in datos),
    )

    return salida


def main(argumentos: list[str] | None = None) -> int:
    from src.conexion_db import cerrar_engine
    from src.registro_logs import configurar_logging

    parser = argparse.ArgumentParser(description="Genera el tablero de operación ETL.")
    parser.add_argument("--salida", type=Path, default=SALIDA_POR_DEFECTO)
    parser.add_argument("--dias", type=int, default=14)
    args = parser.parse_args(argumentos)

    configurar_logging()

    try:
        generar_tablero(args.salida, max(args.dias, 1))
        return 0
    except Exception:
        logger.exception("No se pudo generar el tablero")
        return 1
    finally:
        cerrar_engine()


if __name__ == "__main__":
    raise SystemExit(main())
