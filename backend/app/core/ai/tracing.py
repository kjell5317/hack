import logging
import os
from typing import Any

from haystack import component, tracing
from haystack_integrations.components.connectors.langfuse import LangfuseConnector

from app.core.config import settings

logger = logging.getLogger(__name__)


@component
class SafeLangfuseConnector(LangfuseConnector):
    """LangfuseConnector that doesn't fail the pipeline when Langfuse is unreachable.

    Its run() asks the Langfuse API for the trace URL; a Langfuse outage or a
    wrong key should cost the trace link, not the user's request.
    """

    @component.output_types(name=str, trace_url=str, trace_id=str)
    def run(self, invocation_context: dict[str, Any] | None = None) -> dict[str, str]:
        try:
            return super().run(invocation_context)
        except Exception:
            logger.warning("Langfuse unavailable, continuing without trace link", exc_info=True)
            return {"name": self.name, "trace_url": "", "trace_id": ""}


def langfuse_connector(name: str) -> LangfuseConnector | None:
    """Langfuse tracer for a pipeline, or None if Langfuse isn't configured.

    Once a pipeline with the connector has run, tracing is global: every
    pipeline run shows up in Langfuse, prompts and replies included.
    """
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    # Record component inputs/outputs (prompts, replies), not just timings.
    tracing.tracer.is_content_tracing_enabled = True
    # The default flushes synchronously after every component, which would
    # block the event loop; flush_tracing() runs on shutdown instead.
    os.environ.setdefault("HAYSTACK_LANGFUSE_ENFORCE_FLUSH", "false")
    return SafeLangfuseConnector(name)


def flush_tracing() -> None:
    actual = getattr(tracing.tracer, "actual_tracer", None)
    if hasattr(actual, "flush"):
        actual.flush()
