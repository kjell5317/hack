from pydantic import BaseModel, Field


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4_000)


class ChatOut(BaseModel):
    reply: str
    # The model that answered (can differ from the configured one after a fallback).
    model: str | None = None
    # Link to this run in Langfuse, when tracing is configured.
    trace_url: str | None = None
