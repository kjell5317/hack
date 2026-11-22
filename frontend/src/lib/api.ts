import { supabase } from "@/lib/supabase"

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Calls the FastAPI backend at /api (same origin: Vite proxies it in dev, Caddy
// in prod) with the user's Supabase access token. Throws ApiError with FastAPI's
// `detail` message on non-2xx. Domain-specific calls live in src/domains/*/api.ts.
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const session = (await supabase?.auth.getSession())?.data.session
  if (session) headers.set("Authorization", `Bearer ${session.access_token}`)
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }

  const res = await fetch(`/api${path}`, { ...init, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ApiError(res.status, body?.detail ?? res.statusText)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}
