-- ============================================================
-- V004 - Registro de archivos de origen procesados
-- ------------------------------------------------------------
-- Una fila por archivo y ejecución exitosa. Permite:
-- - Ingesta incremental: omitir archivos ya cargados (por hash,
--   aunque cambien de nombre).
-- - Linaje: saber qué archivos alimentaron cada ejecución (run_id).
-- La escribe la tarea registrar_ingesta (src/ingesta.py).
-- ============================================================

CREATE TABLE IF NOT EXISTS public.etl_archivos_procesados (
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
    ON public.etl_archivos_procesados (pipeline_id, hash_sha256);

CREATE INDEX IF NOT EXISTS ix_etl_archivos_run_id
    ON public.etl_archivos_procesados (run_id);
