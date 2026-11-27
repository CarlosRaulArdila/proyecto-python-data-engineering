-- ============================================================
-- V006 - Historial de registros rechazados
-- ------------------------------------------------------------
-- Una fila por registro rechazado en cada ejecución, con el
-- motivo y el registro original completo (JSON). Antes solo
-- existían CSV que cada ejecución sobrescribía.
-- La escribe la etapa registrar_rechazos (src/rechazos.py).
-- ============================================================

CREATE TABLE IF NOT EXISTS public.etl_rechazos (
    id              BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          UUID         NOT NULL,
    pipeline_id     VARCHAR(100) NOT NULL,
    tipo            VARCHAR(30)  NOT NULL,   -- incompleto | duplicado | conflicto_clave | regla_negocio
    motivo          TEXT         NOT NULL,
    fuente          VARCHAR(100),
    registro        JSONB        NOT NULL,
    fecha_registro  TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_etl_rechazos_run_id
    ON public.etl_rechazos (run_id);

CREATE INDEX IF NOT EXISTS ix_etl_rechazos_pipeline_fecha
    ON public.etl_rechazos (pipeline_id, fecha_registro DESC);

CREATE INDEX IF NOT EXISTS ix_etl_rechazos_tipo
    ON public.etl_rechazos (tipo);
