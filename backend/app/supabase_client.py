from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from supabase import AsyncClient, AsyncClientOptions, acreate_client

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # One shared client for the whole app. It never signs in itself; user
    # tokens are only passed to auth.get_claims() for verification.
    app.state.supabase = await acreate_client(
        settings.supabase_url,
        settings.supabase_secret_key,
        options=AsyncClientOptions(auto_refresh_token=False, persist_session=False),
    )
    yield


def get_supabase(request: Request) -> AsyncClient:
    return request.app.state.supabase


Supabase = Annotated[AsyncClient, Depends(get_supabase)]
