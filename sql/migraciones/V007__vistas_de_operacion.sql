-- V007 - Vistas de operación
-- ============================================================
-- Vistas de operación (capa para tableros y BI)
-- ------------------------------------------------------------
-- Genérica: {{esquema}} = base_datos.esquema y
--           {{zona_horaria}} = orquestacion.zona_horaria.
-- Es el mismo archivo en todos los proyectos.
--
-- vw_etl_ejecuciones       historial enriquecido de ejecuciones
-- vw_etl_salud             estado actual de cada pipeline
-- vw_etl_calidad_diaria    tendencia diaria de volumen y calidad
-- vw_etl_rechazos_resumen  motivos de rechazo más frecuentes
-- vw_etl_linaje            archivos de origen de cada ejecución
--
-- Las herramientas de BI deben consultar estas vistas, no las
-- tablas internas: así los cambios internos no rompen los tableros.
-- ============================================================

CREATE OR REPLACE VIEW {{esquema}}.vw_etl_ejecuciones AS
SELECT
    a.id,
    a.run_id,
    a.proyecto_id,
    a.pipeline_id,
    a.orquestador,
    a.version_pipeline,
    a.ambiente,
    CASE
        WHEN a.estado = 'EXITOSO' AND a.advertencias IS NOT NULL THEN 'ADVERTENCIA'
        ELSE a.estado
    END                                                   AS estado_operativo,
    a.estado,
    a.fecha_inicio,
    a.fecha_fin,
    (a.fecha_inicio AT TIME ZONE '{{zona_horaria}}')      AS fecha_inicio_local,
    a.duracion_segundos,
    a.registros_extraidos,
    a.registros_limpios,
    a.registros_rechazados,
    a.operaciones_bd,
    CASE
        WHEN a.registros_extraidos > 0
        THEN round(100.0 * a.registros_rechazados / a.registros_extraidos, 1)
    END                                                   AS porcentaje_rechazo,
    (
        SELECT count(*)
        FROM {{esquema}}.etl_archivos_procesados f
        WHERE f.run_id = a.run_id
    )                                                     AS archivos_procesados,
    a.mensaje_error,
    a.advertencias
FROM {{esquema}}.etl_auditoria a;


CREATE OR REPLACE VIEW {{esquema}}.vw_etl_salud AS
WITH ultima AS (
    SELECT DISTINCT ON (pipeline_id) *
    FROM {{esquema}}.vw_etl_ejecuciones
    ORDER BY pipeline_id, fecha_inicio DESC
),
exitos AS (
    SELECT pipeline_id, max(fecha_inicio) AS ultimo_exito
    FROM {{esquema}}.etl_auditoria
    WHERE estado = 'EXITOSO'
    GROUP BY pipeline_id
),
semana AS (
    SELECT
        pipeline_id,
        count(*)                                              AS ejecuciones_7d,
        count(*) FILTER (WHERE estado IN ('FALLIDO', 'PARCIAL')) AS fallidas_7d
    FROM {{esquema}}.etl_auditoria
    WHERE fecha_inicio > now() - interval '7 days'
    GROUP BY pipeline_id
)
SELECT
    u.proyecto_id,
    u.pipeline_id,
    CASE
        WHEN u.estado_operativo IN ('FALLIDO', 'PARCIAL')                       THEN 'FALLANDO'
        WHEN u.estado_operativo = 'EN_PROCESO'                                  THEN 'EN_PROCESO'
        WHEN e.ultimo_exito IS NULL
          OR now() - e.ultimo_exito > interval '26 hours'                       THEN 'ATRASADO'
        WHEN u.estado_operativo = 'ADVERTENCIA'                                 THEN 'ADVERTENCIA'
        ELSE 'OK'
    END                                                       AS salud,
    u.estado_operativo                                        AS ultimo_estado,
    u.fecha_inicio                                            AS ultima_ejecucion,
    e.ultimo_exito,
    round(extract(epoch FROM now() - e.ultimo_exito) / 3600, 1) AS horas_desde_ultimo_exito,
    coalesce(s.ejecuciones_7d, 0)                             AS ejecuciones_7d,
    coalesce(s.fallidas_7d, 0)                                AS fallidas_7d,
    u.version_pipeline,
    u.mensaje_error                                           AS ultimo_error,
    u.advertencias                                            AS ultimas_advertencias
FROM ultima u
LEFT JOIN exitos e USING (pipeline_id)
LEFT JOIN semana s USING (pipeline_id);


CREATE OR REPLACE VIEW {{esquema}}.vw_etl_calidad_diaria AS
SELECT
    pipeline_id,
    (fecha_inicio AT TIME ZONE '{{zona_horaria}}')::date               AS dia,
    count(*)                                                          AS ejecuciones,
    count(*) FILTER (WHERE estado = 'EXITOSO')                        AS exitosas,
    count(*) FILTER (WHERE estado IN ('FALLIDO', 'PARCIAL'))          AS fallidas,
    sum(registros_extraidos)                                          AS registros_extraidos,
    sum(registros_rechazados)                                         AS registros_rechazados,
    sum(operaciones_bd)                                               AS operaciones_bd,
    round(100.0 * sum(registros_rechazados)
          / nullif(sum(registros_extraidos), 0), 1)                   AS porcentaje_rechazo,
    round(avg(duracion_segundos), 2)                                  AS duracion_promedio_s
FROM {{esquema}}.etl_auditoria
WHERE estado <> 'EN_PROCESO'
GROUP BY 1, 2;


CREATE OR REPLACE VIEW {{esquema}}.vw_etl_rechazos_resumen AS
SELECT
    pipeline_id,
    tipo,
    motivo,
    fuente,
    count(*)                  AS registros,
    count(DISTINCT run_id)    AS ejecuciones,
    min(fecha_registro)       AS primera_vez,
    max(fecha_registro)       AS ultima_vez
FROM {{esquema}}.etl_rechazos
GROUP BY pipeline_id, tipo, motivo, fuente;


CREATE OR REPLACE VIEW {{esquema}}.vw_etl_linaje AS
SELECT
    a.id                       AS id_ejecucion,
    a.run_id,
    a.pipeline_id,
    a.fecha_inicio,
    a.estado,
    f.fuente,
    f.nombre_archivo,
    f.registros,
    f.tamano_bytes,
    f.hash_sha256,
    f.fecha_registro
FROM {{esquema}}.etl_auditoria a
JOIN {{esquema}}.etl_archivos_procesados f ON f.run_id = a.run_id;
