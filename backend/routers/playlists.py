import asyncio
import io
import json
import os
import zipfile
from pathlib import Path
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import db_path, media_path
from database import get_db
from services.playlist_generator import generate_playlist

router = APIRouter(prefix="/api/playlists", tags=["playlists"])

DB = Annotated[aiosqlite.Connection, Depends(get_db)]


class PlaylistOut(BaseModel):
    id: int
    name: str
    type: str
    m3u_path: str | None
    track_count: int = 0


class CreatePlaylistRequest(BaseModel):
    name: str


class GenerateRequest(BaseModel):
    name: str
    mood: str | None = None
    genre: str | None = None
    limit: int = 50


class AddTrackRequest(BaseModel):
    media_id: int


@router.get("", response_model=list[PlaylistOut])
async def list_playlists(db: DB) -> list[PlaylistOut]:
    async with db.execute(
        "SELECT p.id, p.name, p.type, p.m3u_path,"
        " COUNT(pi.id) AS track_count"
        " FROM playlists p"
        " LEFT JOIN playlist_items pi ON pi.playlist_id = p.id"
        " GROUP BY p.id ORDER BY p.created_at DESC"
    ) as cur:
        rows = await cur.fetchall()
    return [
        PlaylistOut(id=r[0], name=r[1], type=r[2], m3u_path=r[3], track_count=r[4])
        for r in rows
    ]


@router.post("/generate", status_code=201)
async def generate_playlist_endpoint(body: GenerateRequest) -> dict:
    result = await asyncio.to_thread(
        generate_playlist,
        db_path(),
        media_path(),
        body.name,
        body.mood,
        body.genre,
        body.limit,
    )
    return result


@router.post("", status_code=201, response_model=PlaylistOut)
async def create_manual_playlist(body: CreatePlaylistRequest, db: DB) -> PlaylistOut:
    async with db.execute(
        "INSERT INTO playlists (name, type, filter_criteria) VALUES (?, 'manual', ?)",
        (body.name, json.dumps({})),
    ) as cur:
        playlist_id = cur.lastrowid
    await db.commit()
    assert playlist_id is not None
    return PlaylistOut(id=playlist_id, name=body.name, type="manual", m3u_path=None)


@router.post("/{playlist_id}/tracks", status_code=200)
async def add_track(playlist_id: int, body: AddTrackRequest, db: DB) -> dict:
    async with db.execute("SELECT id FROM playlists WHERE id=?", (playlist_id,)) as cur:
        if await cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Playlist not found")

    async with db.execute(
        "SELECT id FROM playlist_items WHERE playlist_id=? AND media_id=?",
        (playlist_id, body.media_id),
    ) as cur:
        if await cur.fetchone() is not None:
            raise HTTPException(status_code=409, detail="Track already in playlist")

    async with db.execute(
        "SELECT COALESCE(MAX(position), -1) FROM playlist_items WHERE playlist_id=?",
        (playlist_id,),
    ) as cur:
        row = await cur.fetchone()
    next_pos = (row[0] if row else -1) + 1

    await db.execute(
        "INSERT INTO playlist_items (playlist_id, media_id, position) VALUES (?, ?, ?)",
        (playlist_id, body.media_id, next_pos),
    )
    await db.commit()
    return {"playlist_id": playlist_id, "media_id": body.media_id, "position": next_pos}


@router.delete("/{playlist_id}", status_code=204)
async def delete_playlist(playlist_id: int, db: DB) -> Response:
    async with db.execute(
        "SELECT m3u_path FROM playlists WHERE id=?", (playlist_id,)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Playlist not found")

    if row[0]:
        m3u_abs = os.path.join(media_path(), row[0])
        try:
            os.remove(m3u_abs)
        except FileNotFoundError:
            pass

    await db.execute("DELETE FROM playlist_items WHERE playlist_id=?", (playlist_id,))
    await db.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
    await db.commit()
    return Response(status_code=204)


@router.get("/{playlist_id}/download")
async def download_playlist_zip(playlist_id: int, db: DB) -> StreamingResponse:
    async with db.execute("SELECT id FROM playlists WHERE id=?", (playlist_id,)) as cur:
        if await cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Playlist not found")

    async with db.execute(
        "SELECT m.file_path, m.title FROM media m"
        " JOIN playlist_items pi ON pi.media_id = m.id"
        " WHERE pi.playlist_id=? ORDER BY pi.position",
        (playlist_id,),
    ) as cur:
        tracks = await cur.fetchall()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path, title in tracks:
            abs_path = Path(media_path()) / file_path
            if abs_path.exists():
                zf.write(abs_path, abs_path.name)
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="playlist.zip"'},
    )
