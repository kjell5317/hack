from typing import Any

from haystack import Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.dataclasses import ChatMessage
from supabase import AsyncClient

from app.ai.components import SupabaseNoteRetriever
from app.ai.tracing import langfuse_connector

ANSWER_PROMPT = [
    ChatMessage.from_system(
        "Answer the question using only the user's notes. "
        "If the notes don't contain the answer, say so in one sentence."
    ),
    ChatMessage.from_user(
        "Notes:\n{% for doc in documents %}- {{ doc.content }}\n{% endfor %}\n"
        "Question: {{ question }}"
    ),
]


def build_ask_pipeline(supabase: AsyncClient, embedder: Any, llm: Any) -> Pipeline:
    """RAG over the user's notes: embed question -> match_notes -> prompt -> LLM.

    Run with run_async (the retriever is async). Inputs:
        {"embedder": {"text": q}, "retriever": {"user_id": uid}, "prompt_builder": {"question": q}}
    """
    pipeline = Pipeline()
    if tracer := langfuse_connector("ask-notes"):
        pipeline.add_component("tracer", tracer)
    pipeline.add_component("embedder", embedder)
    pipeline.add_component("retriever", SupabaseNoteRetriever(supabase))
    pipeline.add_component(
        "prompt_builder",
        ChatPromptBuilder(template=ANSWER_PROMPT, required_variables=["question", "documents"]),
    )
    pipeline.add_component("llm", llm)
    pipeline.connect("embedder.embedding", "retriever.query_embedding")
    pipeline.connect("retriever.documents", "prompt_builder.documents")
    pipeline.connect("prompt_builder.prompt", "llm.messages")
    return pipeline
