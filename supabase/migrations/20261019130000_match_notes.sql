-- Vector search for the backend (supabase.rpc("match_notes", ...)).
-- PostgREST can't ORDER BY a pgvector distance, so it lives in a function.
create function public.match_notes(
  query_embedding extensions.vector(1536),
  match_user_id uuid,
  match_count int default 5
)
returns table (id bigint, content text, created_at timestamptz, similarity float)
language sql
stable
set search_path = ''
as $$
  select
    n.id,
    n.content,
    n.created_at,
    1 - (n.embedding operator(extensions.<=>) query_embedding) as similarity
  from public.notes n
  where n.user_id = match_user_id
  order by n.embedding operator(extensions.<=>) query_embedding
  limit match_count;
$$;

-- Callers pick the user id, so keep it backend-only (the secret key maps to
-- service_role). Browsers with the publishable key can't call it.
revoke execute on function public.match_notes from public, anon, authenticated;
grant execute on function public.match_notes to service_role;
