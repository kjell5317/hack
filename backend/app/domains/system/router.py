"""Health check (used by the deploy smoke test and the UI badge) and the current user."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.auth import CurrentUser, User
from app.core.config import settings
from app.core.supabase import Supabase

router = APIRouter(tags=["system"])


class Health(BaseModel):
    status: str
    database: str
    llm: str
    model: str | None
    tracing: bool


@router.get("/health")
async def health(request: Request, supabase: Supabase) -> Health:
    try:
        # Auth reads Postgres, so this proves URL, secret key, network and database.
        await supabase.auth.admin.list_users(page=1, per_page=1)
        database = "ok"
    except Exception as e:  # noqa: BLE001 - report any failure, don't crash
        database = f"error: {type(e).__name__}"
    return Health(
        status="ok",
        database=database,
        llm=settings.llm_provider_resolved,
        model=request.app.state.llm_model,
        tracing=settings.tracing_enabled,
    )


@router.get("/me")
def me(user: CurrentUser) -> User:
    return user
