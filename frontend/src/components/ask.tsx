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
import { api } from "@/lib/api"

type AskResult = {
  answer: string
  sources: { id: number; content: string; score: number }[]
  trace_url: string | null
}

// Example LLM feature: RAG over your notes (Haystack pipeline on the backend).
export function Ask() {
  const [question, setQuestion] = useState("")
  const [result, setResult] = useState<AskResult | null>(null)
  const [busy, setBusy] = useState(false)

  async function ask(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      setResult(
        await api<AskResult>("/ask", {
          method: "POST",
          body: JSON.stringify({ question }),
        })
      )
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="w-full max-w-xl">
      <CardHeader>
        <CardTitle>Ask your notes</CardTitle>
        <CardDescription>
          Retrieves your closest notes and lets the LLM answer from them.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <form className="flex gap-2" onSubmit={ask}>
          <Input
            placeholder="Ask a question…"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <Button type="submit" disabled={busy || !question.trim()}>
            {busy ? "Thinking…" : "Ask"}
          </Button>
        </form>
        {result && (
          <div className="flex flex-col gap-3 text-sm">
            <p className="whitespace-pre-wrap">{result.answer}</p>
            <div className="flex flex-wrap gap-2">
              {result.sources.map((s) => (
                <Badge key={s.id} variant="outline" title={s.content}>
                  #{s.id} · {s.score.toFixed(2)}
                </Badge>
              ))}
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
