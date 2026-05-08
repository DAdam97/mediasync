from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

import aiosqlite
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import media_path
from database import get_db, init_db
from routers import downloads, library
from services import download_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    await download_manager.retry_interrupted()
    yield


app = FastAPI(title="MediaSync API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory=media_path()), name="media")
app.include_router(downloads.router)
app.include_router(library.router)

DB = Annotated[aiosqlite.Connection, Depends(get_db)]


@app.get("/")
async def root() -> FileResponse:
    return FileResponse("static/index.html")


class HealthResponse(BaseModel):
    status: str


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


class DownloadsByStatus(BaseModel):
    pending: int = 0
    downloading: int = 0
    processing: int = 0
    done: int = 0
    error: int = 0


class StatsResponse(BaseModel):
    total_tracks: int
    storage_used_bytes: int
    downloads_by_status: DownloadsByStatus


@app.get("/api/stats", response_model=StatsResponse)
async def stats(db: DB) -> StatsResponse:
    async with db.execute("SELECT COUNT(*) FROM media") as cur:
        row = await cur.fetchone()
        total_tracks = row[0] if row else 0

    async with db.execute("SELECT COALESCE(SUM(file_size_bytes), 0) FROM media") as cur:
        row = await cur.fetchone()
        storage_used_bytes = row[0] if row else 0

    async with db.execute(
        "SELECT status, COUNT(*) FROM downloads GROUP BY status"
    ) as cur:
        rows = await cur.fetchall()

    counts = {row[0]: row[1] for row in rows}
    by_status = DownloadsByStatus(
        pending=counts.get("pending", 0),
        downloading=counts.get("downloading", 0),
        processing=counts.get("processing", 0),
        done=counts.get("done", 0),
        error=counts.get("error", 0),
    )

    return StatsResponse(
        total_tracks=total_tracks,
        storage_used_bytes=storage_used_bytes,
        downloads_by_status=by_status,
    )
