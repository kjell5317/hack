# hack

**Quick setup:** [Owner: create the repo, add keys, deploy](docs/setup-owner.md) · [Teammate: join and run it](docs/setup-teammate.md)

A starting point for hackathon teams. Sign-in, an LLM wired up for whichever key the hackathon partner hands out, Postgres with vector search, and a production deploy to your own subdomain. Every push to `main` goes live.

- **Frontend**: React 19, Vite, Tailwind v4, shadcn/ui
- **Backend**: FastAPI, Haystack (Anthropic, OpenAI or any OpenAI-compatible API, Gemini), Langfuse tracing
- **Data and auth**: Supabase (Postgres, pgvector, Auth); local in Docker, hosted in production
- **Deploy**: Terraform creates a Hetzner server, a Supabase project, a Cloudflare DNS record and the GitHub secrets; GitHub Actions tests, builds and ships
- **Tests**: pytest (unit and against a real local Supabase), Playwright in the browser, all in CI
- **One CLI** for macOS and Windows: `./hack` (`.\hack` on Windows)
- **AI coding agents**: instructions and task skills for Claude Code and Codex

## How it works

### Local development

`./hack dev` starts Supabase in Docker (Postgres, Auth, Studio at <http://127.0.0.1:54323>). It then starts the backend and frontend with hot reload at <http://localhost:5173>, with API docs at `/api/docs`. Supabase's local keys never go in `.env`; the CLI reads them from the running stack. The header shows whether the backend, the database and the LLM are ready. The **LLM playground** card sends a prompt through the backend and links to its Langfuse trace.

### Keys and the team `.env`

`.env` holds only what people type in. The provider is picked from whichever key is set; `CHAT_MODEL` overrides the model.

| You have | Put it in `.env` |
| --- | --- |
| An Anthropic key | `ANTHROPIC_API_KEY` (model `claude-opus-5-5`) |
| An OpenAI key | `OPENAI_API_KEY` (`gpt-5-mini`) |
| Another OpenAI-compatible API | `OPENAI_API_KEY` + `OPENAI_BASE_URL` |
| A Gemini key | `GOOGLE_API_KEY` (`gemini-3.8-flash`) |
| Langfuse (optional) | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` (+ `LANGFUSE_BASE_URL` for the US region) |

**Sharing.** `./hack env share` encrypts `.env` with [age](https://age-encryption.org) to every repo collaborator's SSH key, which GitHub publishes at `github.com/<user>.keys`, and commits it as `.env.age`. Teammates decrypt it with `./hack env pull`, using the SSH key `./hack setup` put on their GitHub account. No password manager or extra account is needed, and the encrypted file is safe even in a public repo.

### Deploys

`./hack deploy` runs Terraform (`infra/`), which creates:

- the Supabase project;
- the Hetzner server;
- `https://<subdomain>.<zone>`;
- the GitHub secrets, including a copy of `.env` for production.

From then on, every push to `main` runs CI: tests, then images, then database migrations, then deploy over SSH, then a health check. Until the first `./hack deploy`, CI only tests; the image and deploy jobs are skipped. Terraform state stays on the deployer's machine (`infra/terraform.tfstate`, gitignored).

## Everyday commands

| Command | Does |
| --- | --- |
| `./hack dev` / `./hack stop` | Run the app with hot reload / stop it and local Supabase |
| `./hack check` | Lint, backend tests and browser tests, as CI runs them. Run it before you push. |
| `./hack test` / `./hack e2e --ui` | Backend tests / Playwright with its UI |
| `./hack env` / `env fill` / `env share` / `env pull` | Show / fill in / share / receive the team `.env` |
| `./hack db new add_projects` | New SQL migration; `./hack db reset` rebuilds the local database |
| `./hack format` | Auto-format Python and TypeScript |
| `./hack skills` | Copy agent skills to `.claude/skills` after editing them |
| `./hack deploy` / `./hack destroy` | Create or update production / tear it down, including its data |
| `./hack doctor` | Show tool versions and project state |

## Project layout

Code is organized by feature ("domain"). A feature has the same name in every layer:

```text
supabase/migrations/            schema, row level security, SQL functions
backend/app/domains/<feature>/  router.py · schemas.py · repository.py · pipeline.py
frontend/src/domains/<feature>/ api.ts · components
backend/app/core/               config, auth, Supabase client, LLM providers, tracing
frontend/e2e/                   Playwright tests
infra/  deploy/  .github/       Terraform, production compose + Caddy, CI/CD
```

`playground` is the placeholder feature; replace it with your own. The recipe is in [.agents/skills/new-domain](.agents/skills/new-domain/SKILL.md).

## AI coding agents (Claude Code, Codex)

- **[AGENTS.md](AGENTS.md)** has the project's commands, layout and rules. Codex reads it directly; Claude Code reads it through [CLAUDE.md](CLAUDE.md), which only contains `@AGENTS.md`.
- **Skills** are task guides an agent loads only when a task needs them. Until then, it sees just their one-line description.
  - They live in [.agents/skills/](.agents/skills/), which Codex reads.
  - Claude Code reads only `.claude/skills/`, so that folder is a copy made by `./hack skills`. `./hack lint` fails when the copy is stale.
  - Edit the skills in `.agents/skills/` only.

| Skill | The agent uses it for |
| --- | --- |
| `new-domain` | "Add projects that users can create and list": migration with RLS, backend domain, UI, tests |
| `supabase` | Schema, SQL, row level security, sign-in and OAuth, storage, realtime |
| `llm` | Prompts, agents with tools, structured output, RAG with pgvector, switching models, Langfuse |
| `frontend` | UI with shadcn/ui and Tailwind, calling the API, auth state |
| `testing` | Writing and debugging pytest and Playwright tests, CI failures |
| `deploy` | Deploys, production config, logs, rollback, failing deploy jobs |

To run one explicitly, type `/new-domain` in Claude Code, or `$new-domain` in Codex.

## Security

- No secrets are committed. `.env`, `terraform.tfvars` and the state file are gitignored, and `.env.age` is encrypted.
- The backend uses Supabase's secret key and filters every query by the signed-in user. Row level security protects the tables from direct access with the public key.
- Once deployed, the URL is public and sign-up is open. LLM endpoints need a signed-in user, but every user spends the partner's key, so set a spend limit on it.
