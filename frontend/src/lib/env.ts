declare global {
  interface Window {
    __ENV__?: Record<string, string | undefined>
  }
}

const runtime = window.__ENV__ ?? {}

// Prod reads window.__ENV__ (docker/40-env-js.sh), dev reads VITE_* vars.
export const env = {
  supabaseUrl: runtime.SUPABASE_URL || import.meta.env.VITE_SUPABASE_URL || "",
  supabasePublishableKey:
    runtime.SUPABASE_PUBLISHABLE_KEY ||
    import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ||
    "",
}
