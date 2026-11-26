-- ============================================================
-- V001 - Tablas de control del motor ETL (auditoría y linaje)
-- ------------------------------------------------------------
-- Genérica: {{esquema}} se reemplaza por base_datos.esquema.
-- Copie este archivo tal cual al crear un proyecto nuevo.
-- ============================================================

CREATE TABLE IF NOT EXISTS {{esquema}}.etl_auditoria (
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
    ON {{esquema}}.etl_auditoria (fecha_inicio DESC);

CREATE INDEX IF NOT EXISTS ix_etl_auditoria_run_id
    ON {{esquema}}.etl_auditoria (run_id);

CREATE TABLE IF NOT EXISTS {{esquema}}.etl_archivos_procesados (
    id               BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_id      VARCHAR(100) NOT NULL,
    run_id           UUID         NOT NULL,
    fuente           VARCHAR(100) NOT NULL,
    nombre_archivo   TEXT         NOT NULL,
    hash_sha256      CHAR(64)     NOT NULL,
    tamano_bytes     BIGINT,
    registros        INTEGER,
    fecha_registro   TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_etl_archivos_pipeline_hash
    ON {{esquema}}.etl_archivos_procesados (pipeline_id, hash_sha256);

CREATE INDEX IF NOT EXISTS ix_etl_archivos_run_id
    ON {{esquema}}.etl_archivos_procesados (run_id);
