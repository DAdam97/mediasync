import asyncio
import json

from services.mix_parser import parse_tracklist


async def _fetch_metadata(url: str, fetch_comments: bool) -> dict:
    args = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        "--no-warnings",
    ]
    if fetch_comments:
        args += ["--write-comments", "--extractor-args", "youtube:comment_sort=top"]
    args.append(url)

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError("yt-dlp failed to fetch metadata")
    return dict(json.loads(stdout.decode()))


def _best_comment(comments: list[dict]) -> str:
    def score(c: dict) -> int:
        text = c.get("text", "")
        return sum(1 for line in text.splitlines() if " - " in line)

    best = max(comments, key=score, default=None)
    return best.get("text", "") if best else ""


async def extract_tracklist(url: str, fetch_comments: bool = True) -> list[str]:
    meta = await _fetch_metadata(url, fetch_comments)

    chapters: list[dict] | None = meta.get("chapters")
    if chapters:
        titles = [c.get("title", "") for c in chapters if " - " in c.get("title", "")]
        if len(titles) >= 3:
            return titles

    description = meta.get("description", "") or ""
    tracks = parse_tracklist(description)
    if tracks:
        return tracks

    if fetch_comments:
        comments: list[dict] = meta.get("comments") or []
        comment_text = _best_comment(comments)
        tracks = parse_tracklist(comment_text)
        if tracks:
            return tracks

    return []
