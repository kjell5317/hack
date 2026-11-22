"""/api/playground/*: proves the LLM key and Langfuse work. Replace it with your own domain."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from haystack import Pipeline
from haystack.core.errors import PipelineRuntimeError

from app.core.auth import CurrentUser
from app.domains.playground.schemas import ChatIn, ChatOut

router = APIRouter(prefix="/playground", tags=["playground"])


def get_chat_pipeline(request: Request) -> Pipeline:
    # Built once at startup (app/main.py lifespan); None without an LLM key.
    pipeline = request.app.state.chat_pipeline
    if pipeline is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No LLM configured: put an API key in .env (ANTHROPIC_API_KEY, OPENAI_API_KEY "
            "or GOOGLE_API_KEY) and restart",
        )
    return pipeline


@router.post("/chat")
async def chat(
    body: ChatIn,
    user: CurrentUser,  # signed-in users only: every call spends the team's API key
    pipeline: Annotated[Pipeline, Depends(get_chat_pipeline)],
) -> ChatOut:
    try:
        result = await pipeline.run_async({"prompt_builder": {"message": body.message}})
    except PipelineRuntimeError as e:
        # Usually the provider call (bad key, quota, unknown model): say which step failed.
        cause = e.__cause__ or e
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"{e.component_name} failed: {cause}"
        ) from e
    reply = result["llm"]["replies"][0]
    text = reply.text or ""
    if not text and reply.meta.get("finish_reason") == "content_filter":
        text = "The model declined to answer this request."
    return ChatOut(
        reply=text,
        model=reply.meta.get("model"),
        trace_url=result.get("tracer", {}).get("trace_url") or None,
    )
