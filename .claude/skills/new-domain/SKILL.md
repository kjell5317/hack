---
name: new-domain
description: Add a feature to this app end to end the way the codebase is organized - a Supabase migration with RLS, a backend domain (router, schemas, repository, optional Haystack pipeline), a frontend domain (api.ts and components), and tests. Use when asked to build a feature, resource, page or API endpoint, or to replace the playground example.
---

# Adding a domain

A domain is one feature, sliced vertically. It has the same name in every layer:

| Layer | Path | Holds |
|---|---|---|
| Database | `supabase/migrations/<timestamp>_<name>.sql` | tables, RLS policies, SQL functions |
| Backend | `backend/app/domains/<name>/` | `router.py`, `schemas.py`, `repository.py`, optional `pipeline.py` |
| Frontend | `frontend/src/domains/<name>/` | `api.ts`, `<name>-*.tsx` components |
| Tests | `backend/tests/`, `frontend/e2e/<name>.spec.ts` | |

Shared code lives in `backend/app/core/` (config, auth, Supabase client, AI providers) and in `frontend/src/lib/` and `frontend/src/components/ui/`. A domain imports from core, never from another domain's internals. If two domains need the same thing, move it to core.

`playground` is the example to copy. Once a real feature exists, delete it: both `domains/playground` folders, its router in `backend/app/main.py`, its pipeline in the lifespan there, `PlaygroundCard` in `frontend/src/App.tsx`, and `frontend/e2e/playground.spec.ts`.

The examples below use `projects`; rename throughout.

## 1. Migration

```sh
./hack db new projects      # creates supabase/migrations/<timestamp>_projects.sql
```

```sql
create table public.projects (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  name text not null check (char_length(name) between 1 and 200),
  created_at timestamptz not null default now()
);
create index projects_user_id_idx on public.projects (user_id);

-- Browsers hold the publishable key and can query public tables directly
-- through Supabase's REST API; RLS is what keeps other users' rows hidden.
alter table public.projects enable row level security;
create policy "Users read their own projects" on public.projects
  for select to authenticated using ((select auth.uid()) = user_id);
```

Then `./hack db reset`, which rebuilds the local database from all migrations plus `supabase/seed.sql`. Production gets the migration on the next deploy: CI runs `supabase db push`. Never edit a migration that has been deployed; add a new one.

## 2. Backend: `backend/app/domains/projects/`

`repository.py` is the only code that touches the table:

```python
"""Database access for projects. The client uses the secret key, which bypasses
RLS: every function takes the user id and must filter by it."""

from typing import Any
from uuid import UUID

from supabase import AsyncClient


async def list_projects(supabase: AsyncClient, user_id: UUID) -> list[dict[str, Any]]:
    res = await (
        supabase.table("projects")
        .select("id, name, created_at")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


async def create_project(supabase: AsyncClient, user_id: UUID, name: str) -> dict[str, Any]:
    res = await supabase.table("projects").insert({"user_id": str(user_id), "name": name}).execute()
    return res.data[0]
```

`schemas.py` holds the pydantic models for requests and responses (`ProjectIn` with `Field(min_length=1, max_length=200)`, `ProjectOut` with `id`, `name`, `created_at: datetime`).

`router.py` stays thin:

```python
from fastapi import APIRouter

from app.core.auth import CurrentUser
from app.core.supabase import Supabase
from app.domains.projects import repository
from app.domains.projects.schemas import ProjectIn, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects(user: CurrentUser, supabase: Supabase) -> list[ProjectOut]:
    return [ProjectOut.model_validate(r) for r in await repository.list_projects(supabase, user.id)]


@router.post("", status_code=201)
async def create_project(body: ProjectIn, user: CurrentUser, supabase: Supabase) -> ProjectOut:
    row = await repository.create_project(supabase, user.id, body.name)
    return ProjectOut.model_validate(row)
```

- Register the router in `DOMAIN_ROUTERS` in `backend/app/main.py`. It's then served under `/api/projects`, and listed at `/api/docs`.
- A `user: CurrentUser` parameter means the route needs sign-in (401 otherwise). Leave it out only for deliberately public routes.
- For update and delete, filter by `id` **and** `user_id`, and return 404 when no row matched.
- Build long-lived objects (Haystack pipelines, clients) once in `lifespan` in `main.py`, store them on `app.state`, and read them through a dependency. See `get_chat_pipeline` in `domains/playground/router.py`. For LLM work, see the `llm` skill.

## 3. Frontend: `frontend/src/domains/projects/`

`api.ts`: types mirror `schemas.py`, with one function per endpoint:

```ts
import { api } from "@/lib/api"

export type Project = { id: number; name: string; created_at: string }

export const listProjects = () => api<Project[]>("/projects")

export const createProject = (name: string) =>
  api<Project>("/projects", { method: "POST", body: JSON.stringify({ name }) })
```

For components, copy the shape of `domains/playground/playground-card.tsx`: `useState`, `try`/`catch` around the call, and `toast.error((e as Error).message)` on failure, since `api()` throws `ApiError` carrying FastAPI's `detail`. Compose the component in `src/App.tsx`. Give every input a `<Label>` or an `aria-label`: it's needed for accessibility, and the Playwright tests select by it. More in the `frontend` skill.

## 4. Tests

- **Backend unit test** (no database): sign in a fake user with `app.dependency_overrides[current_user] = lambda: User(id=uuid4())`. See `backend/tests/test_ai.py`.
- **Backend integration test** (real local Supabase), in `backend/tests/test_integration.py` style using `signed_in_user()`. Prove that user A can't see user B's rows through the API (the backend filter), and that A's publishable-key client can't either (RLS).
- **E2E**: `frontend/e2e/projects.spec.ts`, with `test.beforeEach(async ({ page }) => { await signUp(page) })` from `./fixtures`. Every test gets a brand-new user, so tests stay independent and can run in parallel.

Run everything with `./hack check`. Details are in the `testing` skill.

## Checklist

- [ ] Migration with RLS enabled and a select policy; `./hack db reset`
- [ ] `backend/app/domains/<name>/` with every repository query filtered by user id
- [ ] Router added to `DOMAIN_ROUTERS`
- [ ] `frontend/src/domains/<name>/api.ts` plus a component, composed in `App.tsx`
- [ ] Tests; `./hack check` passes
