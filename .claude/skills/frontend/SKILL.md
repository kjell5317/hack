---
name: frontend
description: The React frontend in this repo - Vite, React 19, TypeScript, Tailwind v4, shadcn/ui, the typed API client, auth state and runtime config. Use when building or changing UI, adding shadcn components, calling the backend from the browser, styling, theming, or debugging the dev server.
---

# Frontend (`frontend/`)

Vite 8, React 19, TypeScript 6, Tailwind CSS v4, shadcn/ui (style `radix-nova`, lucide icons), sonner toasts, Geist font. In dev it runs in Docker with hot reload on http://localhost:5173 (`./hack dev`). In production nginx serves the built files behind Caddy.

## Layout

```
src/
  App.tsx                 app shell: header, auth gate, composes domain components
  domains/<name>/         a feature's UI + api.ts (auth, system, playground, ...)
  components/ui/          shadcn components, generated: edit them freely, they're ours
  components/theme-provider.tsx   light/dark/system, persisted; press "d" to toggle
  lib/api.ts              api<T>(): calls /api with the user's token, throws ApiError
  lib/supabase.ts         Supabase client, used for auth only
  lib/env.ts              runtime config (window.__ENV__ in prod, VITE_* in dev)
  index.css               Tailwind v4 config and theme tokens (there's no tailwind.config)
e2e/                      Playwright tests (see the testing skill)
```

## Calling the backend

- Add calls to `src/domains/<name>/api.ts` with types that mirror the backend's `schemas.py`:
  ```ts
  export const createProject = (name: string) =>
    api<Project>("/projects", { method: "POST", body: JSON.stringify({ name }) })
  ```
- `api()` adds the Supabase access token, sets the JSON content type, and throws `ApiError(status, detail)` on non-2xx. Show `detail` to the user with `toast.error((e as Error).message)`.
- `/api` is same-origin everywhere (the Vite proxy in dev, Caddy in prod), so there's no CORS and no base URL to configure.
- The browser never talks to the database directly; data goes through FastAPI. The Supabase client is for sign-in, plus Realtime/Storage if you add them deliberately (`supabase` skill).
- Current user: `useSession()` from `src/domains/auth/use-session.ts` gives `session.user.email`, `session.user.id`, or `null`.

## UI

- Add shadcn components with `cd frontend && npx shadcn@latest add dialog table select textarea`. They land in `src/components/ui/`. Import them as `@/components/ui/dialog`.
- Use theme tokens (`bg-background`, `text-muted-foreground`, `border`, `bg-primary`) rather than raw colours, so dark mode works.
- `cn()` (from `@/lib/utils`) merges class names.
- Toasts: `import { toast } from "sonner"`. The `<Toaster />` is already mounted in `App.tsx`.
- Accessibility doubles as the test API: every input gets a `<Label htmlFor>` or an `aria-label`, buttons get visible text, and lists that tests read get an `aria-label`.
- There's no router yet: `App.tsx` switches on auth state. For several pages, add `react-router` (`npm i react-router`) and keep one route component per domain. For heavier data fetching or caching, `@tanstack/react-query` fits on top of `api()`.

## Config and secrets

- Everything in the bundle is public. Never put a secret in frontend code or in a `VITE_*` variable.
- Runtime config is only the Supabase URL and publishable key. In production, `docker/40-env-js.sh` writes them to `/env.js` when the container starts, so one image works everywhere. In dev, `./hack dev` passes `VITE_SUPABASE_*`.

## Conventions and commands

- Prettier (no semicolons, double quotes, sorted Tailwind classes) and ESLint: `./hack format`, `./hack lint`.
- `npm run typecheck` checks the app, `vite.config.ts` and the e2e tests (`tsc -b`).
- Path alias: `@/` points to `src/`.
- Hot reload doesn't fire on Windows: `./hack dev` turns on polling (`WATCH_POLLING`). Run `npm install` on the host for editor types; the container has its own `node_modules`.
