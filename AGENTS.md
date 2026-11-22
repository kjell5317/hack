# hack: hackathon baseline

<!-- Read by Codex and other agents directly, by Claude Code through CLAUDE.md (@AGENTS.md). -->

FastAPI + Haystack backend, React + shadcn/ui frontend, Supabase (Postgres, pgvector, Auth). It deploys to a Hetzner server via Terraform and GitHub Actions; every push to `main` goes live once CI passes.

## Commands

`./hack <command>` on macOS/Linux, `.\hack <command>` on Windows (`scripts/hack.py`). There's no Makefile.

| | |
|---|---|
| `setup` | install tools and dependencies, create or complete `.env`, start local Supabase |
| `env` / `env fill` / `env share` / `env pull` | show `.env` / prompt for empty values / share with or receive from the team (age + GitHub SSH keys) |
| `dev` / `stop` | app on http://localhost:5173 (hot reload, local Supabase) / stop everything |
| `check` | lint + backend tests + Playwright, which is what CI runs. **Run it before pushing.** |
| `skills` | copy `.agents/skills/` to `.claude/skills/` |
| `test`, `e2e`, `lint`, `format` | the parts of `check`; extra args go to pytest / playwright |
| `db new <name>` / `db reset` | new migration file / rebuild the local DB |
| `deploy` / `destroy` | Terraform: create or update production, then deploy `main` / tear it down |

## Layout

```
backend/app/core/        config, auth (CurrentUser), Supabase client, ai/ (LLM providers, embeddings, Langfuse)
backend/app/domains/<x>/ one folder per feature: router.py, schemas.py, repository.py, pipeline.py
backend/app/main.py      DOMAIN_ROUTERS + lifespan (builds pipelines once)
frontend/src/domains/<x>/  the same feature's UI + api.ts; shared code in lib/ and components/ui/
frontend/e2e/            Playwright tests (fixtures.ts: signUp/signIn)
supabase/migrations/     the schema; config.toml is for local Supabase only (CLI 3.x)
infra/                   Terraform: Supabase project, Hetzner server, Cloudflare DNS, GitHub secrets
deploy/                  production compose file + Caddyfile, shipped by CI
scripts/hack.py          the CLI (standard library only)
```

`playground` is a placeholder domain that proves the LLM key and Langfuse work. Replace it with real features.

## Rules

- The backend uses Supabase's **secret key, which bypasses RLS**: every query filters by `user.id`. Every new table in `public` gets `enable row level security`. SQL functions that take a user id are revoked from `anon`/`authenticated`.
- Routes that read user data or call an LLM take `user: CurrentUser`.
- Get LLM components from `app/core/ai/providers.py` (`chat_generator()`, `text_embedder()`); never hard-code a provider, model or key in a domain. Don't send `temperature` to Claude models.
- Domains import from `core`/`lib`, not from each other.
- Secrets live only in `.env` (gitignored; shared encrypted as `.env.age`), `infra/terraform.tfvars` and GitHub secrets. Nothing secret goes in frontend code; the whole bundle is public.
- Never edit a migration that's deployed; add a new one.
- Tests never call real LLM providers (use `MockChatGenerator` or fake components).
- Python: ruff (line length 100). TS: prettier (no semicolons) + eslint. Fix both with `./hack format`.

## Skills

Task guides in `.agents/skills/<name>/SKILL.md`: `new-domain` (add a feature end to end), `supabase`, `llm` (Haystack, providers, RAG, Langfuse), `frontend`, `testing`, `deploy`. Read the matching one before starting such a task.

Edit skills only in `.agents/skills/`. `.claude/skills/` is a generated copy for Claude Code: run `./hack skills` after changing a skill (`./hack lint` fails while the copy is stale).
