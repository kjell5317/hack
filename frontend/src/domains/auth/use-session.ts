import { useEffect, useState } from "react"
import type { Session } from "@supabase/supabase-js"

import { supabase } from "@/lib/supabase"

// The current Supabase session, or null when signed out. Updates on sign-in,
// sign-out and token refresh.
export function useSession() {
  const [session, setSession] = useState<Session | null>(null)

  useEffect(() => {
    if (!supabase) return
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    const { data } = supabase.auth.onAuthStateChange((_event, s) =>
      setSession(s)
    )
    return () => data.subscription.unsubscribe()
  }, [])

  return session
}
