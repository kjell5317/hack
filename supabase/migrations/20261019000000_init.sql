-- Supabase keeps extensions in the `extensions` schema (on its search_path).
create extension if not exists vector with schema extensions;

create table public.notes (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  content text not null,
  -- Size must match EMBEDDING_DIM in backend/app/embeddings.py.
  embedding extensions.vector(1536) not null,
  created_at timestamptz not null default now()
);

create index notes_user_id_idx on public.notes (user_id);
create index notes_embedding_idx on public.notes
  using hnsw (embedding extensions.vector_cosine_ops);

-- The backend connects as the table owner and bypasses RLS. RLS still matters
-- because the publishable key lets any browser query public tables directly
-- via the Supabase REST API. This policy allows read-only access to own rows.
alter table public.notes enable row level security;

create policy "Users can read their own notes"
  on public.notes for select to authenticated
  using ((select auth.uid()) = user_id);
