-- ============================================================
-- V003 - Advertencias en la auditoría (umbrales de calidad)
-- Genérica: {{esquema}} se reemplaza por base_datos.esquema.
-- ============================================================

ALTER TABLE {{esquema}}.etl_auditoria
    ADD COLUMN IF NOT EXISTS advertencias TEXT;
