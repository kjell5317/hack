import { Button } from "@/components/ui/button"
import { Toaster } from "@/components/ui/sonner"
import { AuthForm } from "@/domains/auth/auth-form"
import { useSession } from "@/domains/auth/use-session"
import { PlaygroundCard } from "@/domains/playground/playground-card"
import { BackendStatus } from "@/domains/system/backend-status"
import { supabase, supabaseConfigured } from "@/lib/supabase"

// App shell: header, auth gate, and the signed-in page. Domain UI lives in
// src/domains/<name>/; compose it here.
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
            Supabase is not configured. Start the app with ./hack dev, which
            passes in the local Supabase URL and key.
          </p>
        ) : session ? (
          <div className="flex w-full max-w-xl flex-col gap-6">
            <PlaygroundCard />
          </div>
        ) : (
          <AuthForm />
        )}
      </main>
      <Toaster />
    </div>
  )
}

export default App
