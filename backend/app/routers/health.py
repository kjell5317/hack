from fastapi import APIRouter

from app.auth import CurrentUser, User
from app.supabase_client import Supabase

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health(supabase: Supabase) -> dict[str, str]:
    try:
        await supabase.table("notes").select("id").limit(1).execute()
        database = "ok"
    except Exception as e:  # noqa: BLE001 - report any failure, don't crash
        database = f"error: {type(e).__name__}"
    return {"status": "ok", "database": database}


@router.get("/me")
def me(user: CurrentUser) -> User:
    return user
