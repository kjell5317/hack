import { useEffect, useState } from "react"
import type { Session } from "@supabase/supabase-js"

import { AuthForm } from "@/components/auth-form"
import { Notes } from "@/components/notes"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Toaster } from "@/components/ui/sonner"
import { api } from "@/lib/api"
import { supabase, supabaseConfigured } from "@/lib/supabase"

function useSession() {
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

function BackendStatus() {
  const [status, setStatus] = useState("checking")

  useEffect(() => {
    api<{ status: string; database: string }>("/health")
      .then((h) => setStatus(h.database === "ok" ? "ok" : "db error"))
      .catch(() => setStatus("down"))
  }, [])

  return (
    <Badge variant={status === "ok" ? "secondary" : "destructive"}>
      backend: {status}
    </Badge>
  )
}

export function App() {
  const session = useSession()

  return (
    <div className="flex min-h-svh flex-col">
      <header className="flex items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-3">
          <span className="font-heading font-medium">hack</span>
          <BackendStatus />
        </div>
        {session && (
          <div className="flex items-center gap-3 text-sm">
            <span className="text-muted-foreground">{session.user.email}</span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => supabase?.auth.signOut()}
            >
              Sign out
            </Button>
          </div>
        )}
      </header>
      <main className="flex flex-1 items-start justify-center p-6">
        {!supabaseConfigured ? (
          <p className="max-w-md text-sm text-muted-foreground">
            Supabase is not configured. Set SUPABASE_URL and
            SUPABASE_PUBLISHABLE_KEY in .env and restart.
          </p>
        ) : session ? (
          <Notes />
        ) : (
          <AuthForm />
        )}
      </main>
      <Toaster />
    </div>
  )
}

export default App
