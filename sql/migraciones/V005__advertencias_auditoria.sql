-- ============================================================
-- V005 - Advertencias en la auditoría
-- ------------------------------------------------------------
-- Guarda los umbrales de calidad incumplidos cuando
-- calidad.accion = "advertir" (la ejecución carga igual).
-- ============================================================

ALTER TABLE public.etl_auditoria
    ADD COLUMN IF NOT EXISTS advertencias TEXT;
