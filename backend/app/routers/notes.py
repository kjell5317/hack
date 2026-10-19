from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.ai.embeddings import embed
from app.auth import CurrentUser
from app.supabase_client import Supabase

router = APIRouter(prefix="/notes", tags=["notes"])

# The Supabase client uses the secret key, which bypasses RLS: every query
# below must filter by the current user itself.


class NoteIn(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)


class NoteOut(BaseModel):
    id: int
    content: str
    created_at: datetime


class NoteHit(NoteOut):
    score: float


@router.get("")
async def list_notes(user: CurrentUser, supabase: Supabase) -> list[NoteOut]:
    res = await (
        supabase.table("notes")
        .select("id, content, created_at")
        .eq("user_id", str(user.id))
        .order("created_at", desc=True)
        .execute()
    )
    return [NoteOut.model_validate(row) for row in res.data]


@router.post("", status_code=201)
async def create_note(body: NoteIn, user: CurrentUser, supabase: Supabase) -> NoteOut:
    row = {"user_id": str(user.id), "content": body.content, "embedding": await embed(body.content)}
    res = await supabase.table("notes").insert(row).execute()
    return NoteOut.model_validate(res.data[0])


@router.get("/search")
async def search_notes(
    user: CurrentUser,
    supabase: Supabase,
    q: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
) -> list[NoteHit]:
    # Vector search runs in Postgres; see match_notes in supabase/migrations.
    params = {
        "query_embedding": await embed(q, purpose="query"),
        "match_user_id": str(user.id),
        "match_count": limit,
    }
    res = await supabase.rpc("match_notes", params).execute()
    return [NoteHit(**row, score=row["similarity"]) for row in res.data]
