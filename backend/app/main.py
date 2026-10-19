from fastapi import APIRouter, FastAPI

from app.routers import health, notes

app = FastAPI(title="hack", docs_url="/api/docs", openapi_url="/api/openapi.json")

api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(notes.router)
app.include_router(api)
