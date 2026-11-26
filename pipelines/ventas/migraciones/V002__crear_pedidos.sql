-- ============================================================
-- V002 - Tabla de destino del pipeline de ventas
-- ------------------------------------------------------------
-- Columnas = esquema de config.yaml + columnas técnicas de control.
-- El índice único corresponde a pipeline.clave_negocio (UPSERT).
-- ============================================================

CREATE TABLE IF NOT EXISTS {{esquema}}.pedidos (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pedido_id            VARCHAR(12)    NOT NULL,
    fecha                DATE           NOT NULL,
    cliente_id           VARCHAR(10)    NOT NULL,
    producto             VARCHAR(100)   NOT NULL,
    categoria            VARCHAR(50)    NOT NULL,
    cantidad             INTEGER        NOT NULL,
    precio_unitario      NUMERIC(14, 2) NOT NULL,
    canal                VARCHAR(20)    NOT NULL,
    tienda_origen        VARCHAR(100)   NOT NULL,
    fecha_creacion       TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion  TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_pedidos_clave_negocio UNIQUE (pedido_id, tienda_origen)
);

CREATE INDEX IF NOT EXISTS ix_pedidos_fecha
    ON {{esquema}}.pedidos (fecha);
