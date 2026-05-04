import asyncio
import os
import re
from pathlib import Path
from typing import Any

_YOUTUBE_ID_RE = re.compile(r"[?&]v=([a-zA-Z0-9_-]{11})")


async def fetch_related_urls(url: str, limit: int) -> list[str]:
    match = _YOUTUBE_ID_RE.search(url)
    video_id = match.group(1) if match else ""
    mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"

    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--flat-playlist",
        "--print",
        "url",
        "--playlist-end",
        str(limit),
        "--no-warnings",
        mix_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    lines = [line for line in stdout.decode().splitlines() if line.strip()]
    return lines[:limit]


async def run_download(download_id: int, url: str, media_path: str) -> dict[str, Any]:
    music_dir = Path(media_path) / "music"
    music_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(music_dir / "%(artist)s - %(title)s.%(ext)s")

    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "--embed-metadata",
        "--output",
        output_template,
        "--print",
        "after_move:filepath",
        "--no-playlist",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(stderr.decode().strip() or "yt-dlp failed")

    file_path = stdout.decode().strip()
    if not file_path:
        raise RuntimeError("yt-dlp produced no output file path")

    stat = os.stat(file_path)
    relative_path = str(Path(file_path).relative_to(media_path))

    from mutagen.easyid3 import EasyID3  # type: ignore[import-not-found]
    from mutagen.mp3 import MP3  # type: ignore[import-not-found]

    title = ""
    artist = ""
    duration_seconds = None
    try:
        tags = EasyID3(file_path)
        title = str(tags.get("title", [""])[0])
        artist = str(tags.get("artist", [""])[0])
    except Exception:
        pass

    try:
        duration_seconds = int(MP3(file_path).info.length)
    except Exception:
        pass

    if not title or not artist:
        name = Path(file_path).stem
        parts = name.split(" - ", 1)
        artist = artist or (parts[0] if len(parts) == 2 else "Unknown")
        title = title or (parts[1] if len(parts) == 2 else name)

    return {
        "title": title,
        "artist": artist,
        "file_path": relative_path,
        "file_size_bytes": stat.st_size,
        "duration_seconds": duration_seconds,
    }
