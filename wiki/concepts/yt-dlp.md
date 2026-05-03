---
title: yt-dlp
type: concept
related: [architecture.md]
updated: 2026-05-01
---

# yt-dlp

## What It Is

yt-dlp is a command-line tool for downloading audio/video from YouTube and YouTube Music. It is the download engine at the heart of MediaSync.

## Deno Requirement (2025+)

YouTube began requiring JavaScript execution for some requests in 2025. yt-dlp handles this via the Deno JS runtime. Deno must be installed in the Docker image alongside yt-dlp, otherwise downloads will silently fail or produce errors on certain videos.

Installation in Dockerfile:
```dockerfile
RUN curl -fsSL https://deno.land/install.sh | sh
ENV DENO_INSTALL="/root/.deno"
ENV PATH="$DENO_INSTALL/bin:$PATH"
```

## Accepted URL Formats

Only YouTube and YouTube Music URLs are accepted:
- `https://www.youtube.com/watch?v=...`
- `https://youtu.be/...`
- `https://music.youtube.com/watch?v=...`
- `https://www.youtube.com/playlist?list=...`
- `https://music.youtube.com/playlist?list=...`

All other URLs are rejected with a validation error at the API layer.

## Metadata yt-dlp Provides

yt-dlp extracts the following from YouTube/YouTube Music:
- `title` — track title
- `uploader` / `artist` — artist name (YouTube Music topic channels have clean structured metadata)
- `thumbnail` — cover art URL (downloaded and embedded as ID3 APIC tag)
- `upload_date` — release date

YouTube Music "topic" channels (e.g. `Artist - Topic`) have clean, structured metadata. Regular YouTube video titles may need `"Artist - Title"` parsing heuristics.

## Output Format

yt-dlp downloads the best available audio stream. For YouTube Music this is typically `opus` in a `.webm` container. ffmpeg converts it to `.mp3` after download.

## Known Limitations

- Rate limiting: YouTube may throttle requests if too many downloads happen in quick succession. No retry logic needed for a single-user system, but worth noting.
- Age-restricted or unavailable videos will fail — the error is caught and stored in `downloads.error_message`.
- Playlist downloads: each track in a playlist becomes a separate `downloads` record.
