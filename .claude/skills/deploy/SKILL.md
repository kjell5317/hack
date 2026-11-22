---
name: deploy
description: Production for this app - the first deploy with Terraform (Hetzner server, Supabase project, Cloudflare DNS, GitHub secrets), automatic deploys on push to main, updating production config, logs, rollback, teardown and troubleshooting. Use for anything about deploying, the live demo, infra/, GitHub Actions secrets, or a failing deploy job.
---

# Deploy

```
browser ── https://<subdomain>.<zone> (Cloudflare DNS, not proxied)
            └─ Hetzner server (Ubuntu + Docker), /opt/app
                 Caddy :443 (Let's Encrypt) ── /api/* → backend (FastAPI)
                                            └─ /*     → frontend (nginx)
backend ── hosted Supabase project (Postgres, Auth)  ·  LLM provider  ·  Langfuse
GitHub Actions: test → build images (GHCR) → migrate DB → ssh: compose pull/up → smoke test
```

## First deploy (once, by one person)

1. Prerequisites: accounts at Hetzner, Cloudflare (the zone already there), Supabase and GitHub. `gh auth login`. The repo pushed to GitHub.
2. `./hack deploy`. The first run creates `infra/terraform.tfvars` from the example, with `github_repository` filled in. Fill in the tokens, `supabase_organization_id`, `cloudflare_zone` and `subdomain` (each value's comment says where to get it), then run `./hack deploy` again.
3. Terraform (`infra/`) creates:
   - a Supabase project and its auth settings;
   - a Hetzner server with a firewall;
   - the DNS record;
   - GitHub variables (`DEMO_DOMAIN`, `SUPABASE_PROJECT_REF`) and secrets (`DEPLOY_SSH_KEY`, `PROD_ENV`, `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`).
4. Then `./hack deploy` starts the CI workflow on `main`. Watch it with `gh run watch`; it takes about 5 minutes.

`terraform -chdir=infra apply` works directly too: the GitHub provider falls back to `gh auth token`.

## After that

- **Every push to `main`** runs tests, builds images tagged with the commit SHA, applies new migrations (`supabase db push`), redeploys over SSH, and checks `https://<domain>/api/health` for `"database":"ok"`. Pushes that only touch `*.md`, `.claude/` or `.env.age` don't deploy.
- **Production config** is the repo's `.env` without its `SUPABASE_*` keys, plus the hosted Supabase values, with `LANGFUSE_TRACING_ENVIRONMENT=production`. Terraform writes it into the `PROD_ENV` secret. After changing `.env` (for example a new partner key), run `./hack deploy`: it updates the secret and redeploys.
- **Terraform state** (`infra/terraform.tfstate`) is local and gitignored, and it contains secrets. Infra changes must be run from the machine that holds it, or copy it securely.

## Operating

```sh
ssh root@$(terraform -chdir=infra output -raw ipv4)
cd /opt/app && docker compose ps
docker compose logs -f backend          # or frontend, caddy
docker compose restart backend
```

- **Supabase dashboard**: `terraform -chdir=infra output -raw supabase_dashboard_url`.
- **Rollback**: `git revert <sha> && git push`. Migrations only go forward, so undo a schema change with a new migration. Re-running an older workflow run redeploys that commit's images, but doesn't undo migrations.
- **Teammates' SSH access**: add their `.pub` paths to `ssh_public_key_files` before the server is created. Afterwards, append the keys to `/root/.ssh/authorized_keys` by hand.
- **Teardown**: `./hack destroy` removes the server, the DNS record, the GitHub secrets **and the Supabase project with all its data**.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `deploy` job skipped | The `DEMO_DOMAIN` variable doesn't exist yet: run `./hack deploy`. On a PR it's skipped by design. |
| Terraform: GitHub variable "already exists" (409) | Left over from an earlier setup: `gh variable delete DEMO_DOMAIN` (or the one named), then apply again. |
| `cx23` unavailable | Set `server_type = "cpx22"` in `terraform.tfvars`. |
| Supabase project limit | A free organization allows 2 active projects: pause or delete one, or use a paid org. |
| "Wait for server provisioning" hangs | cloud-init is still installing Docker on a fresh server; it finishes within a few minutes. |
| TLS error right after the first deploy | Caddy is fetching its certificate. The record must point straight at the server (`cloudflare_proxied = false`). |
| Smoke test: `database: error...` | Check `PROD_ENV`: re-run `./hack deploy`, then look at the backend logs. |
| `supabase db push` fails | A migration's SQL is broken. Try it locally with `./hack db reset`, fix it with a new migration. |
| LLM calls fail in production only | The key isn't in `.env` (so not in `PROD_ENV`), or it has a spend limit. Check `/api/health` → `llm`. |

## Security notes

- Once deployed, the URL is public: it appears in the repo's deployments and Actions logs. Sign-up is open, and confirmation is off by default (`auth_email_confirmation`). LLM endpoints require sign-in, but any signed-up user spends the partner's key, so set a spend limit on it.
- SSH (port 22) is open to the internet because GitHub-hosted runners have no fixed IPs. Only key logins work.
