from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db import get_session
from app.embeddings import embed
from app.models import Note

router = APIRouter(prefix="/notes", tags=["notes"])
Session = Annotated[AsyncSession, Depends(get_session)]


class NoteIn(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    created_at: datetime


class NoteHit(NoteOut):
    score: float


@router.get("")
async def list_notes(user: CurrentUser, session: Session) -> list[NoteOut]:
    rows = await session.scalars(
        select(Note).where(Note.user_id == user.id).order_by(Note.created_at.desc())
    )
    return [NoteOut.model_validate(n) for n in rows]


@router.post("", status_code=201)
async def create_note(body: NoteIn, user: CurrentUser, session: Session) -> NoteOut:
    note = Note(user_id=user.id, content=body.content, embedding=await embed(body.content))
    session.add(note)
    await session.commit()
    return NoteOut.model_validate(note)


@router.get("/search")
async def search_notes(
    user: CurrentUser,
    session: Session,
    q: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
) -> list[NoteHit]:
    distance = Note.embedding.cosine_distance(await embed(q)).label("distance")
    rows = await session.execute(
        select(Note, distance).where(Note.user_id == user.id).order_by(distance).limit(limit)
    )
    return [
        NoteHit(**NoteOut.model_validate(note).model_dump(), score=1 - dist) for note, dist in rows
    ]
