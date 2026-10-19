# hack

React + shadcn/ui frontend, FastAPI backend, Supabase (Postgres + pgvector + Auth), deployed to a Hetzner box with Terraform and GitHub Actions.

```
frontend/   Vite + React 19 + Tailwind v4 + shadcn/ui (radix, Nova preset)
backend/    FastAPI + supabase-py (async client), managed with uv
supabase/   config.toml + SQL migrations (the schema lives here)
deploy/     production compose file + Caddyfile (TLS via Let's Encrypt)
infra/      Terraform: Hetzner server, firewall, Cloudflare A record
.github/    CI: lint/test, build images to GHCR, deploy to the demo box
```

The example feature: signed-in users save notes. Each note gets an embedding and goes into a `vector(1536)` column, and search ranks notes by cosine similarity. Everything goes through FastAPI. The browser only talks to Supabase to log in.

## Why Supabase rather than plain Postgres

Supabase *is* Postgres, and pgvector is a built-in extension, so choosing it costs you nothing on embeddings. On top of that you get:

- **Auth.** Email/password, magic links and OAuth with no code of our own. FastAPI only verifies the user's token with `supabase.auth.get_claims()` (`backend/app/auth.py`).
- **Studio.** A table editor, SQL editor and logs, for debugging during the hackathon.
- **A stateless demo server.** The database is hosted, so the Hetzner box can be destroyed and recreated without losing data.

Trade-offs: you depend on the network and a hosted service, and free projects pause after a week without activity. The backend talks to Supabase only through its Python client (REST API + Auth), with no Postgres connection of its own. Leaving Supabase later would mean replacing that data layer and auth.

## Run it locally

Prereqs: Docker, [uv](https://docs.astral.sh/uv/), Node 24, [Supabase CLI](https://supabase.com/docs/guides/cli).

1. `cp .env.example .env` and choose a database:
   - **Hosted (fastest for a team):** create a project at supabase.com and fill in the Option A values. Then run `supabase login`, `make db-link` (once) and `make db-push` to create the tables.
   - **Local/offline:** run `make db-start`, which starts the whole Supabase stack in Docker (several GB of images) and applies migrations. Copy the values from `supabase status` into the Option B block.
2. `make dev`, then open http://localhost:5173. API docs are at http://localhost:5173/api/docs.

For hosted projects, either turn off **Auth → Providers → Email → Confirm email** or expect a confirmation mail on sign-up. Locally, confirmation is already off.

`make help` lists all shortcuts.

## Everyday tasks

| Task | How |
|---|---|
| Change the schema | `make db-new name=add_things`, write SQL in the new file under `supabase/migrations/`, then `make db-push` (hosted) or `supabase migration up` (local). CI applies it to production on deploy. |
| Add UI components | `cd frontend && npx shadcn@latest add dialog table …` |
| Add a backend route | New module in `backend/app/routers/`, register it in `app/main.py`. Protect it with a `user: CurrentUser` parameter. |
| Use a real embedding model | Replace the body of `embed()` in `backend/app/embeddings.py`. If the dimension isn't 1536, change `EMBEDDING_DIM` and the `vector(…)` column together. The placeholder is a hashed bag of words, so the demo works without an API key. |
| Run tests | `make test`. The end-to-end tests run against local Supabase; the commands are at the top of `backend/tests/test_supabase.py`. |
| Queries PostgREST can't express | Write a SQL function in a migration and call it with `supabase.rpc(...)`, as vector search does with `match_notes`. |

Tables in `public` are reachable from the browser through Supabase's REST API with the publishable key. Enable RLS on every new table, as the init migration does. The backend uses the secret key, which bypasses RLS, so every backend query must filter by the current user itself (see `backend/app/routers/notes.py`).

## Deploy the demo

The pipeline on every push to `main`: tests → build `ghcr.io/<owner>/<repo>/{backend,frontend}` → apply migrations → SSH to the server, `docker compose pull && up` → check `/api/health`. The deploy job is skipped until the setup below is done.

1. **Server and DNS.** Create a Cloudflare API token with *Zone:DNS:Edit* (plus *Zone:Read*) and a Hetzner Cloud API token. Then:
   ```sh
   export HCLOUD_TOKEN=... CLOUDFLARE_API_TOKEN=...
   cp infra/terraform.tfvars.example infra/terraform.tfvars   # set cloudflare_zone + subdomain
   make infra-apply
   ```
   This creates an Ubuntu box with Docker, a firewall (22/80/443) and an A record `<subdomain>.<zone>` pointing at the server's IP. Your `~/.ssh/id_ed25519.pub` gets root access, and Terraform generates a separate key for CI. State is local (`infra/terraform.tfstate`, gitignored), so keep it on one machine.
2. **Production config.** Create `.env.production` with the hosted Supabase values (same keys as Option A in `.env.example`).
3. **Wire up GitHub.** Push the repo to GitHub, then run `make gh-setup`. It sets the `DEMO_DOMAIN` variable plus the `DEPLOY_SSH_KEY` and `PROD_ENV` secrets. It then asks you to paste a Supabase access token and the project's database password, which CI uses to run `supabase db push`.
4. Push to `main`, or run the CI workflow manually. Caddy gets the TLS certificate on first start.

To change production config, edit `.env.production`, run `make gh-setup`, and re-run the workflow.

Notes:
- The default server type is `cx23`. Hetzner's cost-optimized types are sometimes sold out; if so, set `server_type = "cpx22"`.
- Leave `cloudflare_proxied = false` unless you need Cloudflare's proxy. If you turn it on, set the `DEPLOY_HOST` repo variable to the server IP (`terraform -chdir=infra output -raw ipv4`), because SSH doesn't pass through the proxy.
- Teammates' keys: add their `.pub` files to `ssh_public_key_files`. The list is only read when the server is created, so for a running box add the keys to `/root/.ssh/authorized_keys` by hand.
