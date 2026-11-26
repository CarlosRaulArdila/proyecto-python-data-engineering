-- ============================================================
-- V001 - Tabla de destino de registros hospitalarios
-- ------------------------------------------------------------
-- Idempotente: puede ejecutarse sobre una base nueva o sobre
-- una base existente creada con la versión anterior del proyecto.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.hospital_registros (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_historia     VARCHAR(20)  NOT NULL,
    fecha               DATE         NOT NULL,
    edad                INTEGER      NOT NULL,
    especialidad        VARCHAR(50)  NOT NULL,
    tecnica_anestesica  VARCHAR(50)  NOT NULL,
    duracion_minutos    INTEGER      NOT NULL,
    hospital_origen     VARCHAR(100) NOT NULL
);

-- La carga incremental (UPSERT) usa ON CONFLICT sobre la clave de
-- negocio, por lo que PostgreSQL exige un índice único sobre ella.
-- Solo se crea si no existe ya un índice único equivalente.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_index i
        JOIN pg_class t     ON t.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'public'
          AND t.relname = 'hospital_registros'
          AND i.indisunique
          AND (
              SELECT array_agg(a.attname::text ORDER BY a.attname)
              FROM pg_attribute a
              WHERE a.attrelid = t.oid
                AND a.attnum = ANY (i.indkey)
          ) = ARRAY['fecha', 'hospital_origen', 'numero_historia']
    ) THEN
        ALTER TABLE public.hospital_registros
            ADD CONSTRAINT uq_hospital_registros_clave_negocio
            UNIQUE (numero_historia, fecha, hospital_origen);
    END IF;
END
$$;
