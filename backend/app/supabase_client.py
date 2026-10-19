from typing import Annotated

from fastapi import Depends, Request
from supabase import AsyncClient, AsyncClientOptions, acreate_client

from app.config import settings


async def create_supabase() -> AsyncClient:
    # One shared client for the whole app (see main.lifespan). It never signs
    # in itself; user tokens are only passed to auth.get_claims() for verification.
    return await acreate_client(
        settings.supabase_url,
        settings.supabase_secret_key,
        options=AsyncClientOptions(auto_refresh_token=False, persist_session=False),
    )


def get_supabase(request: Request) -> AsyncClient:
    return request.app.state.supabase


Supabase = Annotated[AsyncClient, Depends(get_supabase)]
