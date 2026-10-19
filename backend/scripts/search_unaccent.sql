-- ============================================================
-- Búsqueda sin acentos para el módulo de documentos (OSDA)
-- NO modifica ni elimina datos existentes.
-- Solo agrega: extensiones, función auxiliar, columna generada
-- (derivada automáticamente de los datos actuales) e índice.
-- Reversible: DROP INDEX / DROP COLUMN si algún día se retira.
-- ============================================================

-- 1. Extensiones (módulos de Postgres, no tocan datos)
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2. Wrapper IMMUTABLE de unaccent (requisito para columnas generadas e índices)
CREATE OR REPLACE FUNCTION public.f_unaccent(text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
STRICT
AS $$
  SELECT public.unaccent($1);
$$;

-- 3. Columna generada: texto de búsqueda combinado, sin acentos.
--    Se calcula sola a partir de correlativo + asunto + remitente + destinatario.
--    Los documentos NO se modifican ni eliminan.
ALTER TABLE public.documentos
  ADD COLUMN IF NOT EXISTS search_text text
  GENERATED ALWAYS AS (
    public.f_unaccent(
      coalesce(correlativo, '') || ' ' ||
      coalesce(asunto, '') || ' ' ||
      coalesce(remitente, '') || ' ' ||
      coalesce(destinatario, '')
    )
  ) STORED;

-- 4. Índice trigram: búsquedas rápidas tipo *contiene* con muchos documentos
CREATE INDEX IF NOT EXISTS idx_documentos_search_text_trgm
  ON public.documentos
  USING gin (search_text gin_trgm_ops);

-- 5. Recargar caché de esquema de PostgREST
NOTIFY pgrst, 'reload schema';
