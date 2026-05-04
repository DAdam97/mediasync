import asyncio
import os
import re
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from database import db_path, get_db
from services import downloader

router = APIRouter(prefix="/api/downloads", tags=["downloads"])

DB = Annotated[aiosqlite.Connection, Depends(get_db)]

_YOUTUBE_PATTERN = re.compile(
    r"^https?://(www\.)?(youtube\.com/watch\?.*v=|youtu\.be/"
    r"|music\.youtube\.com/watch\?.*v=|youtube\.com/playlist\?.*list="
    r"|music\.youtube\.com/playlist\?.*list=)"
)

_download_semaphore = asyncio.Semaphore(1)

_SELECT_COLS = """
SELECT d.id, d.url, d.status, d.type, d.source, d.error_message,
       m.title, m.artist, m.duration_seconds
FROM downloads d
LEFT JOIN media m ON m.download_id = d.id
"""

_INSERT_MEDIA = """
INSERT INTO media (title, artist, file_path, file_size_bytes,
                   duration_seconds, source_url, download_id, media_type)
VALUES (?, ?, ?, ?, ?, ?, ?, 'music')
"""


def _is_valid_youtube_url(url: str) -> bool:
    return bool(_YOUTUBE_PATTERN.search(url))


def _source_from_url(url: str) -> str:
    return "youtube"


def _row_to_record(r: tuple) -> "DownloadRecord":
    return DownloadRecord(
        id=r[0], url=r[1], status=r[2], mode=r[3], source=r[4], error_message=r[5],
        title=r[6], artist=r[7], duration_seconds=r[8],
    )


class DownloadRequest(BaseModel):
    url: str
    mode: str = "track"
    limit: int = 10


class DownloadRecord(BaseModel):
    id: int
    url: str
    status: str
    mode: str
    source: str
    error_message: str | None = None
    title: str | None = None
    artist: str | None = None
    duration_seconds: int | None = None


async def _process_download(download_id: int, url: str) -> None:
    media_path = os.getenv("MEDIA_PATH", "/mnt/media")
    async with _download_semaphore:
        async with aiosqlite.connect(db_path()) as db:
            await db.execute(
                "UPDATE downloads SET status='downloading',"
                " updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (download_id,),
            )
            await db.commit()
            try:
                result = await downloader.run_download(download_id, url, media_path)

                await db.execute(
                    "UPDATE downloads SET status='processing',"
                    " updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (download_id,),
                )
                await db.commit()

                await db.execute(
                    _INSERT_MEDIA,
                    (
                        result["title"],
                        result["artist"],
                        result["file_path"],
                        result["file_size_bytes"],
                        result["duration_seconds"],
                        url,
                        download_id,
                    ),
                )
                await db.execute(
                    "UPDATE downloads SET status='done',"
                    " updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (download_id,),
                )
                await db.commit()

            except Exception as e:
                await db.execute(
                    "UPDATE downloads SET status='error', error_message=?,"
                    " updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (str(e), download_id),
                )
                await db.commit()


async def retry_interrupted_downloads() -> None:
    rows: list[tuple] = []
    async with aiosqlite.connect(db_path()) as db:
        async with db.execute(
            "SELECT id, url FROM downloads"
            " WHERE status IN ('downloading', 'processing')"
        ) as cur:
            rows = await cur.fetchall()
        if rows:
            await db.execute(
                "UPDATE downloads SET status='pending', updated_at=CURRENT_TIMESTAMP"
                " WHERE status IN ('downloading', 'processing')"
            )
            await db.commit()
    for download_id, url in rows:
        asyncio.create_task(_process_download(download_id, url))


@router.get("", response_model=list[DownloadRecord])
async def list_downloads(db: DB, status: str | None = None) -> list[DownloadRecord]:
    if status is not None:
        async with db.execute(
            _SELECT_COLS + " WHERE d.status = ?",
            (status,),
        ) as cur:
            rows = await cur.fetchall()
    else:
        async with db.execute(_SELECT_COLS) as cur:
            rows = await cur.fetchall()
    return [_row_to_record(r) for r in rows]


@router.get("/{download_id}", response_model=DownloadRecord)
async def get_download(download_id: int, db: DB) -> DownloadRecord:
    async with db.execute(
        _SELECT_COLS + " WHERE d.id = ?",
        (download_id,),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Download not found")
    return _row_to_record(row)


@router.post("", status_code=201)
async def create_download(
    req: DownloadRequest, db: DB, background_tasks: BackgroundTasks
) -> DownloadRecord | list[DownloadRecord]:
    if not _is_valid_youtube_url(req.url):
        raise HTTPException(
            status_code=422, detail="URL must be a YouTube or YouTube Music link"
        )

    source = _source_from_url(req.url)

    if req.mode == "discovery":
        all_urls = await downloader.fetch_related_urls(req.url, req.limit)
        urls = [u for u in all_urls if _is_valid_youtube_url(u)][: req.limit]
        records = []
        for url in urls:
            async with db.execute(
                "INSERT INTO downloads (url, source, type, status)"
                " VALUES (?, ?, 'discovery', 'pending')",
                (url, source),
            ) as cur:
                row_id = cur.lastrowid
            records.append(
                DownloadRecord(
                    id=row_id,
                    url=url,
                    status="pending",
                    mode="discovery",
                    source=source,
                )
            )
            background_tasks.add_task(_process_download, row_id, url)
        await db.commit()
        return records

    async with db.execute(
        "INSERT INTO downloads (url, source, type, status) VALUES (?, ?, ?, 'pending')",
        (req.url, source, req.mode),
    ) as cur:
        row_id = cur.lastrowid
    await db.commit()

    background_tasks.add_task(_process_download, row_id, req.url)

    return DownloadRecord(
        id=row_id, url=req.url, status="pending", mode=req.mode, source=source
    )
