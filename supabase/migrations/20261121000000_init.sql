-- Starting point for this project's schema. Add tables with `./hack db new <name>`.
--
-- pgvector, for embeddings from app/core/ai (always 1536 dimensions, so use
-- `extensions.vector(1536)` columns). Supabase keeps extensions in `extensions`.
create extension if not exists vector with schema extensions;
