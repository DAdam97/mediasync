import io
import os
from typing import Annotated, Literal

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import media_path
from database import get_db

router = APIRouter(prefix="/api/library", tags=["library"])

DB = Annotated[aiosqlite.Connection, Depends(get_db)]


class MediaItem(BaseModel):
    id: int
    title: str
    artist: str | None
    duration_seconds: int | None
    mood: str | None = None
    stream_url: str


class MoodUpdate(BaseModel):
    mood: Literal["energetic", "chill", "sad", "intense"] | None


@router.get("", response_model=list[MediaItem])
async def list_library(
    db: DB,
    mood: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> list[MediaItem]:
    sql = (
        "SELECT id, title, artist, duration_seconds, mood, file_path"
        " FROM media WHERE 1=1"
    )
    params: list[object] = []
    if mood is not None:
        sql += " AND mood=?"
        params.append(mood)
    if search is not None:
        sql += " AND (title LIKE ? OR artist LIKE ?)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")
    sql += " ORDER BY created_at DESC"
    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return [_row_to_item(r) for r in rows]


def _row_to_item(r: aiosqlite.Row) -> MediaItem:
    return MediaItem(
        id=r[0],
        title=r[1],
        artist=r[2],
        duration_seconds=r[3],
        mood=r[4],
        stream_url=f"/media/{r[5]}",
    )


@router.get("/export-csv")
async def export_csv(db: DB) -> StreamingResponse:
    async with db.execute(
        "SELECT file_path, mood FROM media"
        " WHERE mood IS NOT NULL ORDER BY created_at DESC"
    ) as cur:
        rows = await cur.fetchall()

    output = io.StringIO()
    output.write("filename,mood\n")
    for file_path, mood in rows:
        output.write(f"{os.path.basename(file_path)},{mood}\n")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="dataset_labels.csv"'},
    )


@router.patch("/{item_id}", response_model=MediaItem)
async def patch_library_item(item_id: int, body: MoodUpdate, db: DB) -> MediaItem:
    async with db.execute("SELECT id FROM media WHERE id=?", (item_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Track not found")

    await db.execute("UPDATE media SET mood=? WHERE id=?", (body.mood, item_id))
    await db.commit()

    async with db.execute(
        "SELECT id, title, artist, duration_seconds, mood, file_path"
        " FROM media WHERE id=?",
        (item_id,),
    ) as cur:
        updated = await cur.fetchone()
    return _row_to_item(updated)


@router.get("/{item_id}", response_model=MediaItem)
async def get_library_item(item_id: int, db: DB) -> MediaItem:
    async with db.execute(
        "SELECT id, title, artist, duration_seconds, mood, file_path"
        " FROM media WHERE id=?",
        (item_id,),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Track not found")
    return _row_to_item(row)


@router.delete("/{item_id}", status_code=204)
async def delete_library_item(item_id: int, db: DB) -> Response:
    async with db.execute("SELECT file_path FROM media WHERE id=?", (item_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Track not found")

    file_abs = os.path.join(media_path(), row[0])
    try:
        os.remove(file_abs)
    except FileNotFoundError:
        pass

    await db.execute("DELETE FROM media WHERE id=?", (item_id,))
    await db.commit()
    return Response(status_code=204)
