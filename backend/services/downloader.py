import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

_YOUTUBE_ID_RE = re.compile(r"[?&]v=([a-zA-Z0-9_-]{11})")
_REJECT_WORDS = {"sped up", "slowed", "nightcore", "1 hour", "loop", "karaoke"}


async def _run_yt_dlp_flat(url: str, limit: int) -> list[str]:
    args = ["yt-dlp", "--flat-playlist", "--print", "url", "--no-warnings"]
    if limit > 0:
        args += ["--playlist-end", str(limit)]
    args.append(url)
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    lines = [line for line in stdout.decode().splitlines() if line.strip()]
    return lines[:limit] if limit > 0 else lines


async def fetch_playlist_urls(url: str, limit: int) -> list[str]:
    return await _run_yt_dlp_flat(url, 0)


async def fetch_related_urls(url: str, limit: int) -> list[str]:
    match = _YOUTUBE_ID_RE.search(url)
    video_id = match.group(1) if match else ""
    mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
    return await _run_yt_dlp_flat(mix_url, limit)


def select_best_candidate(candidates: list[dict], blacklist_id: str) -> dict | None:
    suitable = []
    for c in candidates:
        if blacklist_id and c.get("id", "") == blacklist_id:
            continue
        duration = c.get("duration") or 0
        if duration < 60 or duration > 600:
            continue
        if any(w in (c.get("title") or "").lower() for w in _REJECT_WORDS):
            continue
        suitable.append(c)
    if not suitable:
        return None
    return next(
        (c for c in suitable if (c.get("uploader") or "").endswith("- Topic")),
        suitable[0],
    )


async def search_and_download(
    query: str, blacklist_id: str, media_path: str
) -> dict[str, Any]:
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        "--no-warnings",
        f"ytsearch5:{query}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()

    candidates: list[dict] = []
    for line in stdout.decode().splitlines():
        line = line.strip()
        if line:
            try:
                candidates.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    best = select_best_candidate(candidates, blacklist_id)
    if best is None:
        raise RuntimeError(f"No suitable result found on YouTube for: {query}")

    url = f"https://www.youtube.com/watch?v={best.get('id', '')}"
    return await run_download(0, url, media_path)


async def run_download(download_id: int, url: str, media_path: str) -> dict[str, Any]:
    music_dir = Path(media_path) / "music"
    music_dir.mkdir(parents=True, exist_ok=True)

    if "music.youtube.com" in url:
        output_template = str(music_dir / "%(artist)s - %(title)s.%(ext)s")
    else:
        output_template = str(music_dir / "%(title)s.%(ext)s")

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

    file_path = stdout.decode().splitlines()[0].strip() if stdout else ""
    if not file_path:
        raise RuntimeError("yt-dlp produced no output file path")

    stat = os.stat(file_path)
    relative_path = str(Path(file_path).relative_to(media_path))

    from mutagen.easyid3 import EasyID3
    from mutagen.mp3 import MP3

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

    if "music.youtube.com" not in url:
        parts = title.split(" - ", 1)
        if len(parts) == 2:
            artist, title = parts[0], parts[1]

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
