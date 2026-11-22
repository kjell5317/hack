---
name: supabase
description: Supabase in this project - local stack, migrations, row level security, auth (email, OAuth), storage, realtime, SQL functions and production. Use when changing the database schema, writing SQL, touching sign-in, adding file uploads or realtime, debugging Supabase errors, or answering where data and users live.
---

# Supabase

Supabase provides Postgres (with pgvector), Auth, Storage and Realtime.

- **Local**: the Supabase CLI runs it in Docker, started by `./hack dev`, `./hack test` and `./hack e2e`. The CLI is pinned at 3.x: CI uses `SUPABASE_CLI_VERSION` in `.github/workflows/ci.yml`, and `./hack setup` installs or upgrades it.
- **Production**: one hosted project, created by Terraform (`infra/supabase.tf`). Its dashboard link: `terraform -chdir=infra output -raw supabase_dashboard_url`.

## Where things are

| | Local | Production |
|---|---|---|
| Schema | `supabase/migrations/*.sql`, applied by `supabase start` / `./hack db reset` | Applied by the CI deploy job (`supabase db push`) |
| Config | `supabase/config.toml` (local only) | `infra/supabase.tf` (`supabase_settings`) and the dashboard |
| Keys | `supabase status`; `./hack dev` injects them, they are **not** in `.env` | GitHub secret `PROD_ENV`, written by Terraform |
| Studio | http://127.0.0.1:54323 | Dashboard |
| Emails | Mailpit at http://127.0.0.1:54324 (nothing is really sent) | Auto-confirmed by default (see Auth) |
| DB URL | `postgresql://postgres:postgres@127.0.0.1:54322/postgres` | Dashboard > Connect |

## The security model (read before writing queries)

- The **browser** uses Supabase only to sign in (`frontend/src/lib/supabase.ts`, with the publishable key). Data goes through FastAPI.
- **FastAPI** uses the **secret key**, which **bypasses RLS** (`backend/app/core/supabase.py`). Every backend query must therefore filter by `user.id` itself.
- RLS is still required on every table in `public`. The publishable key is public, so anyone can call the REST API directly. Enable RLS and add only the policies the browser genuinely needs. A table with RLS enabled and no policies is reachable by the backend only.
- A SQL function that takes a user id as a parameter must be backend-only:
  ```sql
  revoke execute on function public.my_fn from public, anon, authenticated;
  grant execute on function public.my_fn to service_role;
  ```
- Prefer `(select auth.uid())` over `auth.uid()` in policies; it's evaluated once per query instead of per row.

## Migrations

```sh
./hack db new add_tags     # empty migration file to write SQL into
./hack db reset            # rebuild the local DB from migrations + seed.sql (wipes local data)
supabase migration list    # local vs. linked remote
supabase db diff -f name   # turn changes made in Studio into a migration file
```

- Never edit a migration that's already deployed; write a new one.
- Put local test data in `supabase/seed.sql`; it runs on start/reset only, never in production.
- PostgREST (`supabase.table(...)`) can't do everything, for example `order by` a pgvector distance, joins with aggregates, or transactions. Write a SQL function and call it with `await supabase.rpc("fn_name", {...}).execute()`.
- Optional generated TS types: `supabase gen types typescript --local > frontend/src/lib/database.types.ts`.

## Auth

- Email/password is in the UI (`frontend/src/domains/auth/auth-form.tsx`). FastAPI verifies the bearer token with `supabase.auth.get_claims()` in `backend/app/core/auth.py`. Use `CurrentUser` in routes.
- **Email confirmation**: it's off locally. In production Terraform sets `mailer_autoconfirm = true`, because hosted Supabase's built-in SMTP only mails project members (about 2 per hour), so judges couldn't confirm. To require confirmation, configure SMTP first, then set `auth_email_confirmation = true` in `infra/terraform.tfvars`.
- **OAuth** (GitHub, Google, ...):
  - Locally: `[auth.external.github]` in `config.toml`, with `secret = "env(SUPABASE_AUTH_EXTERNAL_GITHUB_SECRET)"`.
  - Production: extend the `auth` JSON in `infra/supabase.tf` (`external_github_enabled`, `external_github_client_id`, `external_github_secret`) or use the dashboard.
  - Frontend: `supabase.auth.signInWithOAuth({ provider: "github", options: { redirectTo: window.location.origin } })`.
  - Redirect URLs: production allows `https://<domain>/**` (Terraform); locally, add them to `additional_redirect_urls`.
- Users are in `auth.users`. Reference them with `user_id uuid references auth.users (id) on delete cascade`.
- Local sign-up/sign-in rate limit is raised to 1000 per 5 minutes for the Playwright tests; production uses Supabase's defaults.

## Storage and Realtime

- **Storage**:
  - Create buckets in a migration so production gets them too: `insert into storage.buckets (id, name, public) values ('uploads', 'uploads', false);`
  - Upload from the backend with `await supabase.storage.from_("uploads").upload(path, data, {"content-type": mime})`.
  - Prefix paths with the user id and check it before you upload or serve.
  - For direct browser uploads, add policies on `storage.objects` instead.
- **Realtime**: `alter publication supabase_realtime add table public.x;`. Clients subscribe with `supabase.channel(...)`. Realtime honours RLS, so the table needs a select policy for the subscribing user.

## Gotchas

- Vector columns: use `extensions.vector(1536)`. The `vector` extension lives in the `extensions` schema (see `supabase/migrations/*_init.sql`); the `llm` skill has the full similarity-search recipe.
- `supabase/config.toml` uses CLI 3.x key names (`[local_smtp]`, `auth.email.enabled`). Check it with `supabase config validate`.
- Free hosted projects pause after a week without traffic, and a free organization allows 2 active projects.
- `/api/health` checks the database through `auth.admin.list_users`, so it works with no tables at all.
