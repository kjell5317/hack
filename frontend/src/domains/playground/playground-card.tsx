import { useState, type FormEvent } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { chat, type ChatResult } from "@/domains/playground/api"

// Proves the LLM key and Langfuse tracing work end to end. Replace it with
// your own feature (see .agents/skills/new-domain).
export function PlaygroundCard() {
  const [message, setMessage] = useState("")
  const [result, setResult] = useState<ChatResult | null>(null)
  const [busy, setBusy] = useState(false)

  async function send(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      setResult(await chat(message))
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="w-full max-w-xl">
      <CardHeader>
        <CardTitle>LLM playground</CardTitle>
        <CardDescription>
          One prompt through the backend&apos;s Haystack pipeline, traced in
          Langfuse when its keys are set.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <form className="flex gap-2" onSubmit={send}>
          <Input
            aria-label="Message"
            placeholder="Say hi to the model…"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
          />
          <Button type="submit" disabled={busy || !message.trim()}>
            {busy ? "Thinking…" : "Send"}
          </Button>
        </form>
        {result && (
          <div className="flex flex-col gap-3 text-sm">
            <p className="whitespace-pre-wrap" aria-label="Reply">
              {result.reply}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {result.model && <Badge variant="outline">{result.model}</Badge>}
              {result.trace_url && (
                <a
                  className="text-muted-foreground underline"
                  href={result.trace_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Langfuse trace
                </a>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
