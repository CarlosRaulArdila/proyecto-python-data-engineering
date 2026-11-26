-- ============================================================
-- V002 - Tabla de auditoría de ejecuciones del pipeline
-- ------------------------------------------------------------
-- Una fila por ejecución. La escriben src/auditoria.py
-- (registrar_inicio / registrar_fin).
-- ============================================================

CREATE TABLE IF NOT EXISTS public.etl_auditoria (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id                UUID          NOT NULL,
    proyecto_id           VARCHAR(100),
    pipeline_id           VARCHAR(100),
    orquestador           VARCHAR(50),
    version_pipeline      VARCHAR(30),
    ambiente              VARCHAR(30),
    estado                VARCHAR(20)   NOT NULL,
    fecha_inicio          TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_fin             TIMESTAMPTZ,
    duracion_segundos     NUMERIC(12, 3),
    registros_extraidos   INTEGER       DEFAULT 0,
    registros_limpios     INTEGER       DEFAULT 0,
    registros_rechazados  INTEGER       DEFAULT 0,
    operaciones_bd        INTEGER       DEFAULT 0,
    archivo_log           TEXT,
    mensaje_error         TEXT
);

CREATE INDEX IF NOT EXISTS ix_etl_auditoria_fecha_inicio
    ON public.etl_auditoria (fecha_inicio DESC);

CREATE INDEX IF NOT EXISTS ix_etl_auditoria_run_id
    ON public.etl_auditoria (run_id);

CREATE INDEX IF NOT EXISTS ix_etl_auditoria_pipeline_estado
    ON public.etl_auditoria (pipeline_id, estado);
