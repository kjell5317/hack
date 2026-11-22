from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.core.ai.providers import chat_generator, chat_model_name
from app.core.ai.tracing import flush_tracing
from app.core.supabase import create_supabase
from app.domains.playground.pipeline import build_chat_pipeline
from app.domains.playground.router import router as playground_router
from app.domains.system.router import router as system_router

# One router per domain (app/domains/<name>/router.py). Register new ones here.
DOMAIN_ROUTERS = [system_router, playground_router]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Long-lived objects go on app.state and are read through dependencies.
    app.state.supabase = await create_supabase()
    llm = chat_generator()
    app.state.llm_model = chat_model_name(llm)
    app.state.chat_pipeline = build_chat_pipeline(llm) if llm else None
    yield
    flush_tracing()


app = FastAPI(
    title="hack", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan
)

api = APIRouter(prefix="/api")
for router in DOMAIN_ROUTERS:
    api.include_router(router)
app.include_router(api)
