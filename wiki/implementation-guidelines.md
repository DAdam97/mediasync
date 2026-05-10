---
title: Implementation Guidelines
type: concept
related: [progress/issues.md]
updated: 2026-05-04
---

# Implementation Guidelines

Lessons learned from past sessions. Read this at the start of every implementation session, before writing any code.

---

## Definition of Done — every issue

Before closing any issue, verify all of these:

- [ ] Tests pass locally (`pytest tests/ -q`)
- [ ] Ruff clean (`ruff check . && ruff format --check .`)
- [ ] Docker image builds (`docker compose build api`)
- [ ] Smoke test inside container passes (see below)
- [ ] Manual API test done (Swagger or curl)
- [ ] Wiki updated, log entry appended, GitHub issue closed

### Docker smoke test (run after every build)
```bash
docker compose exec api yt-dlp --version
docker compose exec api python3 -c "import mutagen; print('ok')"
docker compose exec api python3 -c "import deno" 2>/dev/null || deno --version
```

---

## Recurring Gotchas

### 1. Dockerfile dependencies are invisible to mocked tests
Tests mock yt-dlp subprocess calls — missing binaries or Python packages only surface during manual testing.

**Rule:** When a service calls an external binary or imports a third-party package, add it to both `requirements.txt` AND the Dockerfile smoke test checklist before closing the issue.

Currently required in the Docker image:
- `ffmpeg` (apt)
- `yt-dlp` (binary, downloaded from GitHub releases)
- `deno` (JS runtime, required for YouTube 2025+)
- `mutagen` (pip, ID3 tag read/write)

### 2. yt-dlp flags that must always be present
Missing flags cause silent failures that only appear during real downloads:

| Flag | Why it's needed |
|---|---|
| `--embed-metadata` | Without this, ID3 tags are empty — title/artist show as "Unknown" |
| `--no-playlist` | Without this, a single video URL may trigger full playlist download |
| `--print after_move:filepath` | Required to get the final file path after ffmpeg conversion |
| `--audio-format mp3` | Explicit conversion — default output is opus/webm |

### 3. URL formats — always enumerate in AC
When an issue touches URL validation, the AC must list every accepted format explicitly. Missing formats won't be caught by tests.

Currently accepted:
- `https://www.youtube.com/watch?v=...`
- `https://youtu.be/...`
- `https://music.youtube.com/watch?v=...`
- `https://www.youtube.com/playlist?list=...`
- `https://music.youtube.com/playlist?list=...`

### 4. Concurrency design — decide before coding
If a feature involves background tasks or semaphores, answer these before writing code:
- How many tasks can run concurrently?
- Which layer owns the semaphore (router vs service)?
- Does the status field correctly reflect actual state (not "queued as downloading")?

Current design: semaphore lives in `_process_download` (router layer), status only updates to `downloading` after acquiring the lock.

### 5. `docker compose up -d` does NOT rebuild the image
When Python code changes, the running container still uses the old image unless explicitly rebuilt.

**Rule:** Always use `docker compose up -d --build` after any change to backend Python files or `requirements.txt`. Plain `docker compose up -d` only restarts the existing container and won't pick up code changes.

### 6. yt-dlp `%(artist)s` is the channel name for regular YouTube
For `youtube.com` videos, `%(artist)s` returns the channel name (e.g. "NFrealmusic"), not the actual artist. Only YouTube Music (`music.youtube.com`) has structured artist metadata.

**Rule:** Use `%(title)s.%(ext)s` as the output template for regular YouTube. Use `%(artist)s - %(title)s.%(ext)s` only for YouTube Music. After reading ID3 tags, for non-YouTube-Music URLs split the title string on ` - ` to extract artist and track name.

### 7. DB column name vs API field name mismatch
The `downloads` table uses `type` for the column that the API exposes as `mode`. This is a known inconsistency — do not introduce more like it. When adding new columns, match the API field name exactly.

### 8. Genre tag comes from metadata, not ML
`media.genre` is populated from yt-dlp metadata (YouTube Music official releases typically include genre). For tracks without metadata genre, use KNN inference on audio feature vectors (cosine similarity — no trained model needed). There is no `genre_classifier.tflite` and no plan to train one. Do not add a genre classifier; use the KNN lookup in `services/classifier.py` instead.

### 9. Playlist diversity: MMR, not simple shuffle
Dynamic playlist generation (`POST /api/playlists/generate`) must use Maximal Marginal Relevance (MMR) on audio feature vectors to prevent acoustically similar tracks appearing consecutively. Simple `ORDER BY RANDOM()` is not acceptable — it does not guarantee acoustic variety. No-duplicate constraint is within a single playlist only (same track cannot appear twice); there is no cross-session "recently played" exclusion.

### 10. .m3u files must use relative paths
The Pi generates .m3u playlist files. Use relative paths (e.g. `../music/filename.mp3`), not absolute Pi paths (`/mnt/media/music/filename.mp3`). Absolute paths break on the phone after Syncthing sync because the filesystem layout differs.

---

## Manual Testing Checklist — Download Pipeline

After every change to the download pipeline, test this sequence:

1. `POST /api/downloads` with a valid YouTube URL → expect 201, `status: pending`
2. `GET /api/downloads/{id}` → watch status transition: `pending → downloading → processing → done`
3. `GET /api/library` → track appears with correct title, artist, duration
4. Verify MP3 file exists in `/mnt/usb-ssd/media/music/`
5. Restart the container mid-download → verify it resumes on startup

---

## Session Start Ritual

1. Read `wiki/index.md`
2. Read last 5 entries of `wiki/log.md`
3. Read this file (`wiki/implementation-guidelines.md`)
4. Check open issues: `wiki/progress/issues.md`
