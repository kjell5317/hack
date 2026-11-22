"""The smallest useful Haystack pipeline: prompt -> LLM, traced to Langfuse when configured."""

from typing import Any

from haystack import Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.dataclasses import ChatMessage

from app.core.ai.tracing import langfuse_connector

PROMPT = [
    ChatMessage.from_system(
        "You are the assistant in a hackathon team's app. Answer clearly and briefly."
    ),
    ChatMessage.from_user("{{ message }}"),
]


def build_chat_pipeline(llm: Any) -> Pipeline:
    """Inputs: {"prompt_builder": {"message": text}}. Outputs: llm.replies, tracer.trace_url."""
    pipeline = Pipeline()
    if tracer := langfuse_connector("playground-chat"):
        pipeline.add_component("tracer", tracer)
    pipeline.add_component(
        "prompt_builder", ChatPromptBuilder(template=PROMPT, required_variables=["message"])
    )
    pipeline.add_component("llm", llm)
    pipeline.connect("prompt_builder.prompt", "llm.messages")
    return pipeline
