from fastapi import APIRouter
from sqlalchemy import text

from app.auth import CurrentUser, User
from app.db import engine

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health() -> dict[str, str]:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        database = "ok"
    except Exception as e:  # noqa: BLE001 - report any DB failure, don't crash
        database = f"error: {type(e).__name__}"
    return {"status": "ok", "database": database}


@router.get("/me")
def me(user: CurrentUser) -> User:
    return user
