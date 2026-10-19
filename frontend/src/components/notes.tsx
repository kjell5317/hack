import { useEffect, useState, type FormEvent } from "react"
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
import { api, type Note } from "@/lib/api"

// Example feature: store text with an embedding, then search by similarity.
export function Notes() {
  const [notes, setNotes] = useState<Note[]>([])
  const [draft, setDraft] = useState("")
  const [query, setQuery] = useState("")

  async function load() {
    try {
      setNotes(await api<Note[]>("/notes"))
    } catch (e) {
      toast.error(`Loading notes failed: ${(e as Error).message}`)
    }
  }

  useEffect(() => {
    api<Note[]>("/notes")
      .then(setNotes)
      .catch((e) => toast.error(`Loading notes failed: ${e.message}`))
  }, [])

  async function add(e: FormEvent) {
    e.preventDefault()
    try {
      await api<Note>("/notes", {
        method: "POST",
        body: JSON.stringify({ content: draft }),
      })
      setDraft("")
      setQuery("")
      await load()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  async function search(e: FormEvent) {
    e.preventDefault()
    if (!query.trim()) return load()
    try {
      const params = new URLSearchParams({ q: query })
      setNotes(await api<Note[]>(`/notes/search?${params}`))
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <Card className="w-full max-w-xl">
      <CardHeader>
        <CardTitle>Notes</CardTitle>
        <CardDescription>
          Each note is embedded and stored in pgvector. Search ranks by cosine
          similarity.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <form className="flex gap-2" onSubmit={add}>
          <Input
            placeholder="Write a note…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <Button type="submit" disabled={!draft.trim()}>
            Add
          </Button>
        </form>
        <form className="flex gap-2" onSubmit={search}>
          <Input
            placeholder="Semantic search…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button type="submit" variant="secondary">
            Search
          </Button>
        </form>
        <ul className="flex flex-col gap-2">
          {notes.map((note) => (
            <li
              key={note.id}
              className="flex items-start justify-between gap-4 rounded-md border p-3 text-sm"
            >
              <span>{note.content}</span>
              {note.score !== undefined && (
                <Badge variant="outline">{note.score.toFixed(2)}</Badge>
              )}
            </li>
          ))}
          {notes.length === 0 && (
            <li className="text-sm text-muted-foreground">Nothing here yet.</li>
          )}
        </ul>
      </CardContent>
    </Card>
  )
}
