import asyncio
import re
from collections.abc import Callable, Coroutine
from typing import Any

import aiosqlite
from pydantic import BaseModel

from config import db_path, media_path
from services import downloader, mix_extractor

_YOUTUBE_PATTERN = re.compile(
    r"^https?://(www\.)?(youtube\.com/watch\?.*v=|youtu\.be/"
    r"|music\.youtube\.com/watch\?.*v=|youtube\.com/playlist\?.*list="
    r"|music\.youtube\.com/playlist\?.*list=)"
)

_download_semaphore = asyncio.Semaphore(1)

_INSERT_MEDIA = """
INSERT INTO media (title, artist, file_path, file_size_bytes,
                   duration_seconds, source_url, download_id, media_type)
VALUES (?, ?, ?, ?, ?, ?, ?, 'music')
"""


class InvalidURLError(ValueError):
    pass


class DuplicateDownloadError(ValueError):
    pass


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


async def enqueue(
    url: str, mode: str, limit: int, db: aiosqlite.Connection
) -> list[DownloadRecord]:
    if not _YOUTUBE_PATTERN.search(url):
        raise InvalidURLError("URL must be a YouTube or YouTube Music link")
    source = "youtube"
    if mode == "mix":
        return await _enqueue_mix(url, source, db)
    if mode == "playlist":
        return await _enqueue_expanded(
            url, mode, source, limit, db, downloader.fetch_playlist_urls
        )
    if mode == "discovery":
        return await _enqueue_expanded(
            url, mode, source, limit, db, downloader.fetch_related_urls
        )
    return await _enqueue_track(url, mode, source, db)


async def _enqueue_mix(
    url: str, source: str, db: aiosqlite.Connection
) -> list[DownloadRecord]:
    match = re.search(r"[?&]v=([a-zA-Z0-9_-]{11})", url)
    blacklist_id = match.group(1) if match else ""

    tracks = await mix_extractor.extract_tracklist(url)
    if not tracks:
        error_msg = f"No tracklist found for: {url}"
        async with db.execute(
            "INSERT INTO downloads (url, source, type, status, error_message)"
            " VALUES (?, ?, 'mix', 'error', ?)",
            (url, source, error_msg),
        ) as cur:
            row_id = cur.lastrowid
        await db.commit()
        assert row_id is not None
        return [
            DownloadRecord(
                id=row_id,
                url=url,
                status="error",
                mode="mix",
                source=source,
                error_message=error_msg,
            )
        ]

    records: list[DownloadRecord] = []
    for query in tracks:
        async with db.execute(
            "SELECT id FROM downloads WHERE url=? AND status != 'error'", (query,)
        ) as cur:
            if await cur.fetchone() is not None:
                continue
        parts = query.split(" - ", 1)
        title = parts[1] if len(parts) == 2 else query
        artist = parts[0] if len(parts) == 2 else None
        async with db.execute(
            "INSERT INTO downloads"
            " (url, source, type, status, title, artist, blacklist_id)"
            " VALUES (?, ?, 'mix', 'pending', ?, ?, ?)",
            (query, source, title, artist, blacklist_id),
        ) as cur:
            row_id = cur.lastrowid
        assert row_id is not None
        records.append(
            DownloadRecord(
                id=row_id,
                url=query,
                status="pending",
                mode="mix",
                source=source,
                title=title,
                artist=artist,
            )
        )
    await db.commit()
    return records


async def _enqueue_expanded(
    url: str,
    mode: str,
    source: str,
    limit: int,
    db: aiosqlite.Connection,
    fetch_fn: Callable[[str, int], Coroutine[Any, Any, list[str]]],
) -> list[DownloadRecord]:
    all_urls = await fetch_fn(url, limit)
    urls = [u for u in all_urls if _YOUTUBE_PATTERN.search(u)][:limit]
    records: list[DownloadRecord] = []
    for track_url in urls:
        async with db.execute(
            "SELECT id FROM downloads WHERE url=? AND status != 'error'", (track_url,)
        ) as cur:
            if await cur.fetchone() is not None:
                continue
        async with db.execute(
            "INSERT INTO downloads (url, source, type, status)"
            " VALUES (?, ?, ?, 'pending')",
            (track_url, source, mode),
        ) as cur:
            row_id = cur.lastrowid
        assert row_id is not None
        records.append(
            DownloadRecord(
                id=row_id, url=track_url, status="pending", mode=mode, source=source
            )
        )
    await db.commit()
    return records


async def _enqueue_track(
    url: str, mode: str, source: str, db: aiosqlite.Connection
) -> list[DownloadRecord]:
    async with db.execute(
        "SELECT id FROM downloads WHERE url=? AND status != 'error'", (url,)
    ) as cur:
        if await cur.fetchone() is not None:
            raise DuplicateDownloadError("URL already queued or downloaded")
    async with db.execute(
        "INSERT INTO downloads (url, source, type, status) VALUES (?, ?, ?, 'pending')",
        (url, source, mode),
    ) as cur:
        row_id = cur.lastrowid
    assert row_id is not None
    await db.commit()
    return [DownloadRecord(id=row_id, url=url, status="pending", mode=mode, source=source)]


async def execute_download(download_id: int) -> None:
    async with _download_semaphore:
        async with aiosqlite.connect(db_path()) as db:
            async with db.execute(
                "SELECT url, type, blacklist_id FROM downloads WHERE id=?",
                (download_id,),
            ) as cur:
                row = await cur.fetchone()
            if row is None:
                return
            url, dl_type, blacklist_id = (
                str(row[0]),
                str(row[1]),
                str(row[2] or ""),
            )

            await db.execute(
                "UPDATE downloads SET status='downloading',"
                " updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (download_id,),
            )
            await db.commit()
            try:
                if dl_type == "mix":
                    result = await downloader.search_and_download(
                        url, blacklist_id, media_path()
                    )
                else:
                    result = await downloader.run_download(
                        download_id, url, media_path()
                    )

                await db.execute(
                    "UPDATE downloads SET status='processing', title=?, artist=?,"
                    " updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (result["title"], result["artist"], download_id),
                )
                await db.commit()

                async with db.execute(
                    "SELECT id FROM media WHERE file_path=?", (result["file_path"],)
                ) as cur:
                    existing = await cur.fetchone()
                if existing is None:
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
                    "UPDATE downloads SET status='done', error_message=NULL,"
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


async def retry_interrupted() -> None:
    async with aiosqlite.connect(db_path()) as db:
        async with db.execute(
            "SELECT id FROM downloads"
            " WHERE status IN ('downloading', 'processing', 'error', 'pending')"
        ) as cur:
            rows = await cur.fetchall()
        if rows:
            await db.execute(
                "UPDATE downloads SET status='pending', error_message=NULL,"
                " updated_at=CURRENT_TIMESTAMP"
                " WHERE status IN ('downloading', 'processing', 'error')"
            )
            await db.commit()
    for (download_id,) in rows:
        asyncio.create_task(execute_download(download_id))
