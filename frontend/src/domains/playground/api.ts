// Typed calls for the playground domain (backend/app/domains/playground/router.py).
import { api } from "@/lib/api"

export type ChatResult = {
  reply: string
  model: string | null
  trace_url: string | null
}

export const chat = (message: string) =>
  api<ChatResult>("/playground/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  })
