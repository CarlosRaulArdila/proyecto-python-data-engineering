-- ============================================================
-- V003 - Columnas técnicas de control en la tabla de destino
-- ------------------------------------------------------------
-- fecha_creacion:      cuándo se insertó el registro.
-- fecha_actualizacion: cuándo cambió por última vez (la actualiza
--                      el UPSERT de src/cargar_incremental.py).
-- Permiten cargas incrementales aguas abajo (BI, data marts).
-- ============================================================

ALTER TABLE public.hospital_registros
    ADD COLUMN IF NOT EXISTS fecha_creacion
        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE public.hospital_registros
    ADD COLUMN IF NOT EXISTS fecha_actualizacion
        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_hospital_registros_fecha_actualizacion
    ON public.hospital_registros (fecha_actualizacion);
