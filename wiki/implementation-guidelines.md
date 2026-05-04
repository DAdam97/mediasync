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

### 5. DB column name vs API field name mismatch
The `downloads` table uses `type` for the column that the API exposes as `mode`. This is a known inconsistency — do not introduce more like it. When adding new columns, match the API field name exactly.

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
