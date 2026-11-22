---
name: testing
description: How to test this app - backend unit and integration tests (pytest against local Supabase), browser end-to-end tests (Playwright), the CLI's tests and what CI runs. Use when writing or fixing tests, debugging a failing CI job, or verifying a change works before pushing.
---

# Testing

| What | Where | Run | Needs |
|---|---|---|---|
| Everything CI checks | | `./hack check` | Docker (Supabase is started for you) |
| Lint, types | | `./hack lint` | |
| Backend unit + integration | `backend/tests/` | `./hack test` (args go to pytest: `./hack test -k chat -x`) | local Supabase for integration |
| Browser E2E | `frontend/e2e/` | `./hack e2e` (`--ui`, `--headed`, `-g "name"`) | local Supabase |
| The `./hack` CLI | `scripts/test_hack.py` | `uv run --with pytest pytest scripts` | `age` for the share/pull test |

`main` deploys automatically once CI passes, so run `./hack check` before pushing.

## Backend (pytest)

- `tests/conftest.py` sets dummy Supabase env vars and provides `client`, a `TestClient` that runs the app's lifespan.
- **Unit tests** don't touch the network:
  - Fake the signed-in user with `app.dependency_overrides[current_user] = lambda: User(id=uuid.uuid4())`, and `.clear()` it afterwards (a fixture does this in `test_ai.py`).
  - Fake LLMs: `MockChatGenerator(response_fn=...)`, or a small `@component` class with `run()` returning `{"replies": [ChatMessage...]}`. Swap `client.app.state.<pipeline>` and restore it afterwards.
  - Swap config with `monkeypatch.setattr(settings, "field", value)`.
- **Integration tests** run against real local Supabase. They're skipped unless `RUN_SUPABASE_TESTS=1`, which `./hack test` sets along with the URL and keys. Create users with `signed_in_user()` (in `test_integration.py`), which returns a real access token. Use random emails so runs never collide.
- For each new table, prove both that the API doesn't return another user's rows and that the user's publishable-key client can't read them (RLS).

## Browser (Playwright)

- `frontend/playwright.config.ts` starts **its own** backend (:8180) and Vite (:5180) against **local** Supabase, with `LLM_PROVIDER=none`. Results don't depend on `./hack dev`, your `.env`, or which keys you have. Only Chromium.
- `e2e/fixtures.ts`:
  - `signUp(page)` signs up a brand-new user through the UI and returns the credentials.
  - `signIn(page, user)` signs an existing user in.
  - The `user` fixture is a signed-in page plus its credentials.
  - Use `test.beforeEach(({ page }) => signUp(page))` so every test has its own user; tests run in parallel.
- Selectors: `getByRole("button", { name: "Send" })`, `getByLabel("Message")`, `getByText(...)`. Avoid CSS selectors; if an element is hard to select, give it a label in the component (that's also an accessibility fix).
- Second user in one test: `const other = await browser.newPage(); await signUp(other)`. It gets a separate context with its own storage.
- Debugging:
  - `./hack e2e --ui` (watch mode, time travel), `./hack e2e --headed --debug`.
  - On failure, traces and screenshots go to `frontend/test-results/`: open them with `npx playwright show-trace <zip>`, or the report with `npx playwright show-report`.
  - In CI, download the `playwright-report` artifact from the failed run.
- Each test signs up users, so local Supabase's auth rate limit is raised in `supabase/config.toml` (`sign_in_sign_ups`).

## CI (`.github/workflows/ci.yml`)

- `backend`: ruff, pytest with Supabase.
- `frontend`: eslint, `tsc -b`, build.
- `e2e`: Playwright.
- `cli`: the `./hack` wrappers on Windows and macOS.
- `terraform`: fmt, validate.
- On `main` after those pass: `images` builds and pushes to GHCR, then `deploy` runs (see the `deploy` skill).

Reproduce a CI failure locally with the same command (`./hack check`). CI pins the Supabase CLI version in `SUPABASE_CLI_VERSION`.
