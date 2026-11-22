import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"

type Health = {
  status: string
  database: string
  llm: string
  model: string | null
  tracing: boolean
}

// Header badges: is the backend + database up, and which LLM is configured.
export function BackendStatus() {
  const [health, setHealth] = useState<Health | null>(null)
  const [down, setDown] = useState(false)

  useEffect(() => {
    api<Health>("/health")
      .then(setHealth)
      .catch(() => setDown(true))
  }, [])

  const status = down
    ? "down"
    : !health
      ? "checking"
      : health.database === "ok"
        ? "ok"
        : "db error"

  return (
    <div className="flex items-center gap-2">
      <Badge
        variant={status === "ok" ? "secondary" : "destructive"}
        aria-label={`Backend status: ${status}`}
      >
        {status}
      </Badge>
      {health && (
        <Badge variant="outline" aria-label={`LLM: ${health.llm}`}>
          {health.llm === "none" ? "no LLM key" : (health.model ?? health.llm)}
          {health.tracing && " · traced"}
        </Badge>
      )}
    </div>
  )
}
