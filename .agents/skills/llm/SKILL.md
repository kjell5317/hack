---
name: llm
description: Build LLM features in this backend with Haystack - providers (Anthropic, OpenAI or compatible, Gemini), prompt pipelines, agents with tools, structured output, embeddings and pgvector similarity search, and Langfuse tracing. Use when adding anything that calls a model, changing the model or provider, debugging LLM errors or traces, or adding RAG/semantic search.
---

# LLM features (Haystack + Langfuse)

## Configuration (`.env`)

| Variable | Effect |
|---|---|
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` | Paste the partner's key. With `LLM_PROVIDER=auto` the first key that's set wins, checked in the order anthropic, openai, gemini. |
| `LLM_PROVIDER` | `auto` (default), `anthropic`, `openai`, `gemini` or `none` |
| `CHAT_MODEL` | Overrides the default: `claude-opus-5-5`, `gpt-5-mini` or `gemini-3.8-flash` |
| `OPENAI_BASE_URL` | An OpenAI-compatible partner API (its key goes in `OPENAI_API_KEY`) |
| `EMBEDDING_PROVIDER` | `auto` (default: OpenAI or Gemini if their key is set, else `hash`), `openai`, `gemini`, `hash` |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` | Tracing is on when both keys are set |

`/api/health` and the header badge show the active provider and model. A changed `.env` takes effect after restarting `./hack dev`. For production, run `./hack deploy`, which writes `PROD_ENV`.

## Code map

- `backend/app/core/ai/providers.py`: `chat_generator()` and `text_embedder(purpose)`. **Always get components from here**, never construct a provider's class in a domain; that way switching provider keeps working.
- `backend/app/core/ai/embeddings.py`: `await embed(text, purpose="document" | "query")`.
- `backend/app/core/ai/tracing.py`: `langfuse_connector(name)` returns a tracer component, or None when Langfuse isn't configured.
- `backend/app/domains/playground/`: the reference: a pipeline built once in `lifespan`, an endpoint that runs it.

## Pattern: a prompt pipeline

```python
from haystack import Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.dataclasses import ChatMessage

from app.core.ai.tracing import langfuse_connector

PROMPT = [
    ChatMessage.from_system("You summarize meeting notes for a busy team."),
    ChatMessage.from_user("Notes:\n{{ notes }}\n\nWrite three bullet points."),
]


def build_summary_pipeline(llm) -> Pipeline:
    pipeline = Pipeline()
    if tracer := langfuse_connector("summarize"):   # named trace in Langfuse
        pipeline.add_component("tracer", tracer)
    pipeline.add_component("prompt_builder", ChatPromptBuilder(template=PROMPT, required_variables=["notes"]))
    pipeline.add_component("llm", llm)
    pipeline.connect("prompt_builder.prompt", "llm.messages")
    return pipeline
```

- Build it in `lifespan` (`backend/app/main.py`) with `chat_generator()`, store it on `app.state`, and return 503 from the dependency when it's `None` (no key).
- Run it with `result = await pipeline.run_async({"prompt_builder": {"notes": text}})`. The reply is `result["llm"]["replies"][0]`, with `.text` and `.meta["model"]`.
- Wrap calls in `except PipelineRuntimeError as e` and raise 502 with `e.component_name` and `e.__cause__`; see `domains/playground/router.py`. Bad keys and quota errors surface this way.
- An empty `.text` together with `meta["finish_reason"] == "content_filter"` means the model refused.
- Prompts are Jinja: loop with `{% for d in documents %}...{% endfor %}`.

## Agents with tools

```python
from haystack.components.agents import Agent
from haystack.dataclasses import ChatMessage
from haystack.tools import tool


@tool
def get_weather(city: str) -> str:
    """Current weather for a city."""        # the docstring is the tool description
    return f"Sunny in {city}"


agent = Agent(chat_generator=chat_generator(), tools=[get_weather], system_prompt="Be brief.")
result = await agent.run_async(messages=[ChatMessage.from_user("Weather in Berlin?")])
answer = result["last_message"].text      # also: messages, step_count, tool_call_counts
```

Tools that need the current user or a database should be built per request, for example closures over `user.id` and `supabase`. Then the model can never choose whose data to read.

## Structured output

The approach that works with every provider: ask for JSON matching a schema in the prompt (include `Model.model_json_schema()`), then validate with `Model.model_validate_json(reply.text)` and retry once on `ValidationError`. Provider-native alternatives exist, but they tie you to one provider:

- OpenAI: `generation_kwargs={"response_format": Model}`.
- Anthropic: `generation_kwargs={"output_config": {"effort": "medium", "format": {"type": "json_schema", "schema": Model.model_json_schema()}}}`. Keep `effort` in it: it replaces the default `output_config`.

## Anthropic specifics (`providers.py`)

- The default model is `claude-opus-5-5`, with `max_tokens=16000`.
- Effort is set to `medium`: lower it for quick chat, raise it (`high`/`xhigh`) for hard reasoning. Thinking is adaptive and can't be disabled on this model.
- Don't send `temperature`, `top_p` or `top_k`; current Claude models reject them with a 400.
- Server-side refusal fallback is on: the `fallbacks: "default"` body field plus the `server-side-fallback-2026-07-01` beta header. A declined request is re-run on Anthropic's recommended fallback model, and `meta["model"]` then names the model that answered. `ClaudeChatGenerator` exists only so Haystack passes `extra_body` through.
- Anthropic has no embeddings API, so with only an Anthropic key, embeddings fall back to `hash` (keyword hashing).

## Embeddings and similarity search (RAG)

Every provider embeds into 1536 dimensions (`EMBEDDING_DIM`), so one column type fits all. Vectors from different models aren't comparable, so after switching provider, re-embed the stored rows.

```sql
create table public.docs (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  content text not null,
  embedding extensions.vector(1536) not null
);
create index on public.docs using hnsw (embedding extensions.vector_cosine_ops);
alter table public.docs enable row level security;

-- PostgREST can't order by a vector distance, so search runs in a function.
create function public.match_docs(query_embedding extensions.vector(1536), match_user_id uuid, match_count int default 5)
returns table (id bigint, content text, similarity float)
language sql stable set search_path = '' as $$
  select d.id, d.content, 1 - (d.embedding operator(extensions.<=>) query_embedding)
  from public.docs d where d.user_id = match_user_id
  order by d.embedding operator(extensions.<=>) query_embedding limit match_count;
$$;
-- It takes a user id, so keep it backend-only.
revoke execute on function public.match_docs from public, anon, authenticated;
grant execute on function public.match_docs to service_role;
```

```python
row = {"user_id": str(user.id), "content": text, "embedding": await embed(text)}
await supabase.table("docs").insert(row).execute()
params = {
    "query_embedding": await embed(question, purpose="query"),
    "match_user_id": str(user.id),
    "match_count": 5,
}
hits = (await supabase.rpc("match_docs", params).execute()).data   # [{id, content, similarity}]
```

For RAG, put the hits into the prompt (`{% for d in documents %}`). To do it inside the pipeline, write a small `@component` retriever with an async `run_async` that calls the rpc.

## Langfuse

- With keys set, every run of a pipeline that has the tracer is traced: prompts, replies, token counts, latency. `result["tracer"]["trace_url"]` links to the run.
- Content tracing is on, so **users' inputs are stored in Langfuse**. Keep that in mind for sensitive data.
- `LANGFUSE_TRACING_ENVIRONMENT` separates dev from production (deploys set `production`).
- A wrong key or a Langfuse outage costs only the trace link (`SafeLangfuseConnector`); the request itself still succeeds.

## Tests and cost

- Never call real providers in tests. Use `MockChatGenerator(response_fn=lambda msgs: ...)` from `haystack.components.generators.chat`, or a tiny `@component` fake (see `RefusingLLM` and `FailingLLM` in `backend/tests/test_ai.py`). Playwright starts the backend with `LLM_PROVIDER=none`.
- Every LLM endpoint takes `user: CurrentUser`, because anyone who reaches the deployed URL could otherwise spend the partner's key. Set a spend limit on the key.
