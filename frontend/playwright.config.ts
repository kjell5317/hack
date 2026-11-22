import { execSync } from "node:child_process"
import { defineConfig, devices } from "@playwright/test"

// Browser tests against the real stack: Vite + FastAPI + local Supabase.
//
// - Always local Supabase, never a hosted project, so
//   test users don't pile up in a hosted database.
// - Own ports and LLM_PROVIDER=none, so results don't depend on `./hack dev`
//   running or on which LLM key you have.

const WEB_PORT = 5180
const API_PORT = 8180

// `./hack e2e` passes these in; otherwise ask the Supabase CLI. Read once in
// the main process; workers inherit process.env.
if (!process.env.E2E_SUPABASE_URL) {
  let status: Record<string, string>
  try {
    status = JSON.parse(
      execSync("supabase status -o json", {
        cwd: "..",
        stdio: ["ignore", "pipe", "ignore"],
      }).toString()
    )
  } catch {
    throw new Error("Local Supabase isn't running. Use ./hack e2e (starts it).")
  }
  process.env.E2E_SUPABASE_URL = status.API_URL
  process.env.E2E_SUPABASE_PUBLISHABLE_KEY = status.PUBLISHABLE_KEY
  process.env.E2E_SUPABASE_SECRET_KEY = status.SECRET_KEY
}

const CI = !!process.env.CI

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  reporter: CI
    ? [["github"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `uv run uvicorn app.main:app --port ${API_PORT}`,
      cwd: "../backend",
      url: `http://localhost:${API_PORT}/api/health`,
      reuseExistingServer: !CI,
      env: {
        SUPABASE_URL: process.env.E2E_SUPABASE_URL!,
        SUPABASE_SECRET_KEY: process.env.E2E_SUPABASE_SECRET_KEY!,
        // No LLM and no tracing, whatever your shell or .env has.
        LLM_PROVIDER: "none",
        LANGFUSE_PUBLIC_KEY: "",
        LANGFUSE_SECRET_KEY: "",
      },
    },
    {
      command: `npm run dev -- --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: !CI,
      env: {
        API_PROXY_TARGET: `http://localhost:${API_PORT}`,
        VITE_SUPABASE_URL: process.env.E2E_SUPABASE_URL!,
        VITE_SUPABASE_PUBLISHABLE_KEY:
          process.env.E2E_SUPABASE_PUBLISHABLE_KEY!,
      },
    },
  ],
})
