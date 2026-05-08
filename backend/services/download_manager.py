import asyncio

import aiosqlite

from config import db_path, media_path
from services import downloader

_download_semaphore = asyncio.Semaphore(1)

_INSERT_MEDIA = """
INSERT INTO media (title, artist, file_path, file_size_bytes,
                   duration_seconds, source_url, download_id, media_type)
VALUES (?, ?, ?, ?, ?, ?, ?, 'music')
"""


async def process_download(download_id: int, url: str) -> None:
    async with _download_semaphore:
        async with aiosqlite.connect(db_path()) as db:
            await db.execute(
                "UPDATE downloads SET status='downloading',"
                " updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (download_id,),
            )
            await db.commit()
            try:
                result = await downloader.run_download(download_id, url, media_path())

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
            "SELECT id, url FROM downloads"
            " WHERE status IN ('downloading', 'processing', 'error')"
        ) as cur:
            rows = await cur.fetchall()
        if rows:
            await db.execute(
                "UPDATE downloads SET status='pending', error_message=NULL,"
                " updated_at=CURRENT_TIMESTAMP"
                " WHERE status IN ('downloading', 'processing', 'error')"
            )
            await db.commit()
    for download_id, url in rows:
        asyncio.create_task(process_download(download_id, url))
