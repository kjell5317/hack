from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from haystack import Pipeline
from haystack.core.errors import PipelineRuntimeError
from pydantic import BaseModel, Field

from app.auth import CurrentUser

router = APIRouter(tags=["ai"])


def get_ask_pipeline(request: Request) -> Pipeline:
    pipeline = request.app.state.ask_pipeline
    if pipeline is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No LLM configured: set LLM_PROVIDER and its API key",
        )
    return pipeline


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


class Source(BaseModel):
    id: int
    content: str
    score: float


class AskOut(BaseModel):
    answer: str
    sources: list[Source]
    # Link to this run in Langfuse, when tracing is configured.
    trace_url: str | None = None


@router.post("/ask")
async def ask(
    body: AskIn, user: CurrentUser, pipeline: Annotated[Pipeline, Depends(get_ask_pipeline)]
) -> AskOut:
    try:
        result = await pipeline.run_async(
            {
                "embedder": {"text": body.question},
                "retriever": {"user_id": str(user.id)},
                "prompt_builder": {"question": body.question},
            },
            include_outputs_from={"retriever"},
        )
    except PipelineRuntimeError as e:
        # Usually the provider call (bad key, quota, unknown model): say which step failed.
        cause = e.__cause__ or e
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"{e.component_name} failed: {cause}"
        ) from e
    docs = result["retriever"]["documents"]
    return AskOut(
        answer=result["llm"]["replies"][0].text or "",
        sources=[Source(id=int(d.id), content=d.content or "", score=d.score or 0) for d in docs],
        trace_url=result.get("tracer", {}).get("trace_url") or None,
    )
