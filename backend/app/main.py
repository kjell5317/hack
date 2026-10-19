from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.ai.pipelines import build_ask_pipeline
from app.ai.providers import chat_generator, text_embedder
from app.ai.tracing import flush_tracing
from app.routers import ask, health, notes
from app.supabase_client import create_supabase


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.supabase = await create_supabase()
    llm = chat_generator()
    app.state.ask_pipeline = (
        build_ask_pipeline(app.state.supabase, text_embedder("query"), llm) if llm else None
    )
    yield
    flush_tracing()


app = FastAPI(
    title="hack", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan
)

api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(notes.router)
api.include_router(ask.router)
app.include_router(api)
