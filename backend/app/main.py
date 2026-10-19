from fastapi import APIRouter, FastAPI

from app.routers import health, notes
from app.supabase_client import lifespan

app = FastAPI(
    title="hack", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan
)

api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(notes.router)
app.include_router(api)
