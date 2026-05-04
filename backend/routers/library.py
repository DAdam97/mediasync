from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database import get_db

router = APIRouter(prefix="/api/library", tags=["library"])

DB = Annotated[aiosqlite.Connection, Depends(get_db)]


class MediaItem(BaseModel):
    id: int
    title: str
    artist: str | None
    file_path: str
    mood: str | None = None


@router.get("", response_model=list[MediaItem])
async def list_library(db: DB) -> list[MediaItem]:
    async with db.execute(
        "SELECT id, title, artist, file_path, mood FROM media ORDER BY created_at DESC"
    ) as cur:
        rows = await cur.fetchall()
    return [
        MediaItem(id=r[0], title=r[1], artist=r[2], file_path=r[3], mood=r[4])
        for r in rows
    ]
