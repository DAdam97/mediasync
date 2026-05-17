from typing import Annotated

import aiosqlite
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from database import get_db
from services import download_queue
from services.download_queue import DownloadRecord

router = APIRouter(prefix="/api/downloads", tags=["downloads"])

DB = Annotated[aiosqlite.Connection, Depends(get_db)]

_SELECT_COLS = """
SELECT d.id, d.url, d.status, d.type, d.source, d.error_message,
       COALESCE(m.title, d.title), COALESCE(m.artist, d.artist), m.duration_seconds
FROM downloads d
LEFT JOIN media m ON m.download_id = d.id
"""


def _row_to_record(r: aiosqlite.Row) -> DownloadRecord:
    return DownloadRecord(
        id=r[0],
        url=r[1],
        status=r[2],
        mode=r[3],
        source=r[4],
        error_message=r[5],
        title=r[6],
        artist=r[7],
        duration_seconds=r[8],
    )


class DownloadRequest(BaseModel):
    url: str
    mode: str = "track"
    limit: int = 10


@router.delete("/{download_id}", status_code=204)
async def delete_download(download_id: int, db: DB) -> None:
    async with db.execute(
        "SELECT status FROM downloads WHERE id = ?", (download_id,)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Download not found")
    if str(row[0]) in ("downloading", "processing"):
        raise HTTPException(status_code=409, detail="Cannot delete an active download")
    await db.execute("DELETE FROM downloads WHERE id = ?", (download_id,))
    await db.commit()


@router.post("/{download_id}/retry", response_model=DownloadRecord)
async def retry_download(
    download_id: int, db: DB, background_tasks: BackgroundTasks
) -> DownloadRecord:
    async with db.execute(
        "SELECT id FROM downloads WHERE id = ? AND status = 'error'",
        (download_id,),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404, detail="Download not found or not in error state"
        )
    await db.execute(
        "UPDATE downloads SET status='pending', error_message=NULL,"
        " updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (download_id,),
    )
    await db.commit()
    background_tasks.add_task(download_queue.execute_download, download_id)
    async with db.execute(_SELECT_COLS + " WHERE d.id = ?", (download_id,)) as cur:
        updated = await cur.fetchone()
    assert updated is not None
    return _row_to_record(updated)


@router.get("", response_model=list[DownloadRecord])
async def list_downloads(db: DB, status: str | None = None) -> list[DownloadRecord]:
    _orphan_filter = " AND (d.status != 'done' OR m.id IS NOT NULL)"
    if status is not None:
        async with db.execute(
            _SELECT_COLS + " WHERE d.status = ?" + _orphan_filter,
            (status,),
        ) as cur:
            rows = await cur.fetchall()
    else:
        async with db.execute(_SELECT_COLS + " WHERE 1=1" + _orphan_filter) as cur:
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
    try:
        records = await download_queue.enqueue(req.url, req.mode, req.limit, db)
    except download_queue.InvalidURLError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except download_queue.DuplicateDownloadError as e:
        raise HTTPException(status_code=409, detail=str(e))

    for r in records:
        if r.status == "pending":
            background_tasks.add_task(download_queue.execute_download, r.id)

    if req.mode in ("mix", "playlist", "discovery"):
        return records
    return records[0]
