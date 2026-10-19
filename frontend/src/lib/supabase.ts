import { createClient } from "@supabase/supabase-js"

import { env } from "@/lib/env"

export const supabaseConfigured = Boolean(
  env.supabaseUrl && env.supabasePublishableKey
)

// Used for auth only; app data goes through the FastAPI backend (src/lib/api.ts).
export const supabase = supabaseConfigured
  ? createClient(env.supabaseUrl, env.supabasePublishableKey)
  : null
