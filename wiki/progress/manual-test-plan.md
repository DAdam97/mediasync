---
title: Manual Test Plan — Issues #2–#5
type: progress
related: [issues.md, ../implementation-guidelines.md]
updated: 2026-05-05
---

# Manual Test Plan — Issues #2–#5

Comprehensive step-by-step manual test plan for everything built so far. Run this top to bottom when testing from home. Each section lists the expected result — if you see something different, the feature is broken.

---

## 0. Prerequisites — Before You Start

### 0.1 Start the stack

```bash
# From the project root (where docker-compose.yml lives)
docker compose up --build -d
```

Wait ~30 seconds, then check:

```bash
docker compose ps
```

**Expected:** `mediasync-api-1` shows `Up` and `healthy` (or at least `Up`). No `Exit` status.

**If it fails:** `docker compose logs api` — look for Python import errors or missing packages.

### 0.2 Check logs are clean

```bash
docker compose logs api --tail 30
```

**Expected:** Lines like:
```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

No `ERROR` or `CRITICAL` lines.

### 0.3 Open browser

Navigate to: `http://localhost:8000`

**Expected:** The MediaSync web UI loads — you see a URL input field, mode buttons (Track / Discovery / Playlist), and an empty download queue section.

### 0.4 Open Swagger UI (keep this tab open throughout)

Navigate to: `http://localhost:8000/docs`

**Expected:** FastAPI Swagger docs load, listing all `/api/downloads`, `/api/library`, `/api/health`, `/api/stats` endpoints.

---

## 1. Health & Stats Endpoints (Issue #2)

### 1.1 Health check

In Swagger UI, click `GET /api/health` → Try it out → Execute.

**Expected response:**
```json
{"status": "ok"}
```
HTTP 200.

Or with curl:
```bash
curl http://localhost:8000/api/health
```

### 1.2 Stats endpoint — empty state

`GET /api/stats` → Execute.

**Expected response shape:**
```json
{
  "total_tracks": 0,
  "downloads_by_status": {},
  "storage_used_bytes": 0
}
```
(Exact field names may vary, but must include track count and download counts.)

HTTP 200. No 500 errors.

---

## 2. URL Validation (Issue #3)

These tests verify that invalid URLs are rejected before any download starts.

### 2.1 Invalid URLs — must be rejected

In Swagger, `POST /api/downloads` → Try it out → paste each body below → Execute:

| Body | Expected status |
|---|---|
| `{"url": "https://spotify.com/track/123"}` | 422 |
| `{"url": "https://soundcloud.com/artist/track"}` | 422 |
| `{"url": "not-a-url-at-all"}` | 422 |
| `{"url": ""}` | 422 |
| `{"url": "https://google.com"}` | 422 |

For each: **Expected response:** HTTP 422 with a `detail` field mentioning "YouTube".

### 2.2 Valid URLs — must be accepted (returns 201, not downloaded yet)

With `_noop` it won't download — but in the real environment it will actually start downloading. Just POST and immediately check status = `pending` before it transitions.

| URL format | Expected |
|---|---|
| `https://www.youtube.com/watch?v=dQw4w9WgXcQ` | 201, status `pending` |
| `https://youtu.be/dQw4w9WgXcQ` | 201, status `pending` |
| `https://music.youtube.com/watch?v=dQw4w9WgXcQ` | 201, status `pending` |

**Note:** These will immediately start downloading for real. The Pi will try to fetch the video. Rick Astley's "Never Gonna Give You Up" (`dQw4w9WgXcQ`) is a good stable test video — it's public, short enough to download quickly (~3.5 min), and has clean metadata.

---

## 3. Single Track Download — Full Flow (Issue #3)

This is the core pipeline. Run it once with a real URL and watch every transition.

### 3.1 Submit a single track

In the **web UI** (`http://localhost:8000`):

1. Paste `https://www.youtube.com/watch?v=dQw4w9WgXcQ` into the URL field.
2. Ensure the mode is **Track** (should auto-select, or click the Track button).
3. Click **Download**.

**Expected immediately:**
- A download card appears in the queue with status badge `pending` (yellow).
- The form clears.

### 3.2 Watch status transitions

The UI polls every 3 seconds. Watch the badge on the card:

| Badge | Color | Meaning |
|---|---|---|
| `pending` | Yellow | Queued, not yet started |
| `downloading` | Blue | yt-dlp is fetching audio |
| `processing` | Blue | ffmpeg + mutagen writing tags |
| `done` | Green | Complete |

**Expected sequence:** `pending` → `downloading` → `processing` → `done`

This usually takes 30–90 seconds depending on Pi speed and network.

**If it stays `pending` forever:** The semaphore may be stuck. Check `docker compose logs api --tail 20`.

**If it goes straight to `error`:** Hover or look for the error message on the card. Common causes:
- yt-dlp outdated → `docker compose exec api yt-dlp -U`
- Deno missing → check `docker compose exec api deno --version`

### 3.3 Verify the download record via API

After status is `done`, in Swagger: `GET /api/downloads` → Execute.

**Expected:** One record with:
- `"status": "done"`
- `"title": "Never Gonna Give You Up"` (or similar)
- `"artist": "Rick Astley"`
- `"duration_seconds"` populated (should be around 212)
- `"error_message": null`

### 3.4 Verify the library entry

`GET /api/library` → Execute.

**Expected:** One item with:
- `"title": "Never Gonna Give You Up"`
- `"artist": "Rick Astley"`
- `"file_path"` pointing to `music/...`
- `"duration_seconds"` populated

### 3.5 Verify the MP3 file on disk

```bash
docker compose exec api ls /mnt/media/music/
```

**Expected:** An `.mp3` file with the artist and title in the filename, e.g.:
```
Rick Astley - Never Gonna Give You Up.mp3
```

### 3.6 Verify ID3 tags

```bash
docker compose exec api python3 -c "
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
import os, glob
files = glob.glob('/mnt/media/music/*.mp3')
if not files:
    print('NO FILES FOUND')
else:
    f = files[0]
    tags = ID3(f)
    print('Title:', tags.get('TIT2'))
    print('Artist:', tags.get('TPE1'))
    print('Has thumbnail:', 'APIC:' in tags or any(k.startswith('APIC') for k in tags.keys()))
"
```

**Expected:**
```
Title: TIT2(encoding=..., text=['Never Gonna Give You Up'])
Artist: TPE1(encoding=..., text=['Rick Astley'])
Has thumbnail: True
```

---

## 4. Error State + Retry (Issue #3 + fix)

### 4.1 Trigger an error state

To get an error, submit a URL for a video that doesn't exist or is private. The easiest approach: submit a valid-looking but nonexistent video ID.

In Swagger, `POST /api/downloads`:
```json
{"url": "https://www.youtube.com/watch?v=XXXXXXXXXXX"}
```

**Expected:** 201, `status: pending`. Then within ~30 seconds the status transitions to `error` and an `error_message` is populated.

### 4.2 Verify error state in UI

In the web UI, the card should show a red `error` badge and the error message text below it.

`GET /api/downloads/{id}` in Swagger:

**Expected:**
- `"status": "error"`
- `"error_message"` is not null and contains something meaningful

### 4.3 Retry the failed download

In the web UI, click the **Retry** button on the error card.

**Expected:**
- The card badge immediately changes to `pending`.
- `"error_message"` clears to null (check via `GET /api/downloads/{id}`).
- The download restarts and will transition to `downloading`.

Since the video doesn't exist, it will fail again. That's expected — we're testing the retry mechanism, not the download success.

Alternatively, retry via API:

```bash
curl -X POST http://localhost:8000/api/downloads/{id}/retry
```

**Expected:** HTTP 200 with the download record showing `status: pending`.

### 4.4 Retry on non-error download returns 404

Take the `id` of a `done` download from Test 3. Try to retry it:

```bash
curl -X POST http://localhost:8000/api/downloads/{done_id}/retry
```

**Expected:** HTTP 404.

### 4.5 Retry on nonexistent ID returns 404

```bash
curl -X POST http://localhost:8000/api/downloads/99999/retry
```

**Expected:** HTTP 404.

---

## 5. Discovery Mode (Issue #3 extra)

Discovery mode queues tracks related to a seed URL by fetching the YouTube Mix playlist.

### 5.1 Submit a discovery request via web UI

1. Paste `https://www.youtube.com/watch?v=dQw4w9WgXcQ` into the URL field.
2. Click the **Discovery** mode button.
3. Set limit to `3` (the "Tracks to queue:" field).
4. Click **Download**.

**Expected:**
- 3 download cards appear in the queue, all `pending`.
- Each card shows a different YouTube URL (the related videos).
- All cards have `mode: discovery` (check via `GET /api/downloads`).

**Note:** This calls yt-dlp against the real YouTube Mix — it may fail if YouTube changes the Mix URL format. If all 3 come back as `error` immediately, the Mix URL construction may need updating.

### 5.2 Verify via API

`GET /api/downloads` → filter by the discovery records.

**Expected:** Multiple records with `"mode": "discovery"`, all with different URLs.

### 5.3 Limit enforcement

Submit discovery with `limit=2`:

**Expected:** Exactly 2 cards appear, not more.

---

## 6. Playlist URL Expansion (Issue #4)

### 6.1 Submit a playlist URL via web UI

1. Paste a public YouTube playlist URL into the field, e.g.:
   `https://www.youtube.com/playlist?list=PLbpi6ZahtOH6Ar_3GPy3workEEj3z9rW`
   (This is a public playlist — feel free to use any public playlist you know.)
2. The mode should **automatically switch to Playlist** when you paste the URL (the Playlist button should activate).
3. Set the limit to `3` in the "Tracks to queue:" field.
4. Click **Download**.

**Expected:**
- 3 download cards appear, all `pending`, mode `playlist`.
- Each card has a different YouTube watch URL (individual track URLs, not the playlist URL itself).

### 6.2 Verify individual track URLs in API

`GET /api/downloads` → look at the newly created records.

**Expected:**
- Each record has `url` like `https://www.youtube.com/watch?v=...` (individual watch URLs).
- `"mode": "playlist"` on all of them.
- `"status": "pending"`.

### 6.3 Auto-mode-switch verification

1. Click the **Track** button to switch back to track mode.
2. Paste a playlist URL again.

**Expected:** The mode selector automatically switches back to **Playlist**.

1. Delete the pasted URL and paste a regular watch URL.

**Expected:** Mode switches back to **Track** (or stays on Track — auto-switch only triggers for playlist URLs).

### 6.4 Playlist limit enforcement

Submit a playlist URL with `limit=2`.

**Expected:** Exactly 2 cards appear.

---

## 7. Cancel Pending Download (Issue #4)

### 7.1 Cancel a pending download

The best moment to test this: right after submitting a playlist or discovery request (multiple `pending` items in queue before any start downloading).

1. Submit a playlist URL with `limit=5` (so there are 5 pending items).
2. Immediately click the **Cancel** button (×) on one of the pending cards.

**Expected:**
- The card disappears from the UI.
- `GET /api/downloads/{id}` returns HTTP 404 (the record is deleted).

### 7.2 Verify via API

Before cancelling, note the `id` of the pending download. After clicking Cancel:

```bash
curl http://localhost:8000/api/downloads/{id}
```

**Expected:** HTTP 404.

### 7.3 Cancel non-pending download returns 404

Try to cancel a `done` download:

```bash
curl -X DELETE http://localhost:8000/api/downloads/{done_id}
```

**Expected:** HTTP 404.

### 7.4 Cancel nonexistent download returns 404

```bash
curl -X DELETE http://localhost:8000/api/downloads/99999
```

**Expected:** HTTP 404.

---

## 8. Status Filtering (Issue #3)

### 8.1 Filter downloads by status

After running several downloads (some pending, some done, some error):

```bash
curl "http://localhost:8000/api/downloads?status=pending"
curl "http://localhost:8000/api/downloads?status=done"
curl "http://localhost:8000/api/downloads?status=error"
```

**Expected:** Each returns only records matching that status. No cross-contamination.

---

## 9. Server Restart — Interrupted Downloads Resume (Issue #3 + fix)

This test verifies that a download interrupted by a container restart is retried on startup.

### 9.1 Start a download and restart mid-flight

1. Submit a single track download.
2. Watch until the badge shows `downloading`.
3. Immediately run:
   ```bash
   docker compose restart api
   ```
4. Wait for the container to come back up (~10 seconds).

**Expected:**
- On restart, any download that was in `downloading` or `processing` state is reset to `pending` and re-queued.
- Within ~30 seconds, the download resumes and completes to `done`.
- The UI shows the status updating again after the restart.

**What to check in logs:**
```bash
docker compose logs api --tail 30
```
Look for lines indicating interrupted downloads were detected and re-queued.

---

## 10. Web UI Smoke Test (Issue #5)

Run through the full UI flow without using the API directly.

### 10.1 Empty state

Open `http://localhost:8000` in a fresh browser tab (no prior downloads in DB — or use an in-memory DB by restarting the container with a fresh volume).

**Expected:**
- URL input field is present.
- Three mode buttons: Track, Discovery, Playlist.
- Track mode is active by default.
- Download queue section is empty (no cards).
- No JavaScript errors in the browser console (F12 → Console tab).

### 10.2 Submit and see card

1. Paste `https://www.youtube.com/watch?v=dQw4w9WgXcQ`.
2. Click Download.

**Expected:**
- The card appears immediately (before polling).
- URL field clears after submit.
- No page reload.

### 10.3 Polling behaviour — stops when idle

After all downloads reach `done` or `error`:

**Expected:** The UI stops polling (no more network requests visible in DevTools → Network tab). Open DevTools and watch — after all items are terminal (done/error), no more requests to `/api/downloads` are made.

### 10.4 Polling restarts on next submit

After polling stopped, submit another URL.

**Expected:** Polling restarts (requests to `/api/downloads` appear again in Network tab).

### 10.5 Enter key submits

Type a URL in the input field, press Enter.

**Expected:** Same as clicking Download.

### 10.6 Invalid URL error display

Type `https://spotify.com/track/123` and click Download.

**Expected:**
- A form-level error message appears below the input or the button (e.g. "URL must be a YouTube or YouTube Music link").
- No download card is created.
- The error message disappears when you submit a valid URL next time.

### 10.7 Status badge colors

Observe the badge colors during a download:

| Status | Expected badge color |
|---|---|
| `pending` | Yellow / orange |
| `downloading` | Blue |
| `processing` | Blue |
| `done` | Green |
| `error` | Red |

### 10.8 Cancel button visible only on pending

**Expected:**
- Pending cards show a Cancel (×) button.
- Done cards do NOT show a Cancel button.
- Error cards do NOT show a Cancel button, but show a Retry button.

---

## 11. Docker Smoke Tests (Implementation Guidelines)

Run these after every Docker build:

```bash
# yt-dlp is installed and runnable
docker compose exec api yt-dlp --version

# mutagen is importable
docker compose exec api python3 -c "import mutagen; print('ok')"

# Deno runtime is available
docker compose exec api deno --version

# ffmpeg is installed
docker compose exec api ffmpeg -version | head -1

# aiosqlite and fastapi are importable
docker compose exec api python3 -c "import aiosqlite, fastapi; print('ok')"
```

**All expected to print a version string or "ok" — no import errors.**

---

## 12. Full End-to-End Regression Run

Run this sequence in order after any significant change:

1. `docker compose up --build -d` — fresh build
2. `GET /api/health` → `{"status": "ok"}`
3. `GET /api/stats` → valid JSON
4. POST invalid URL → 422
5. POST valid YouTube URL → 201, then wait for `done`
6. `GET /api/library` → track appears with title/artist/duration
7. File exists in `docker compose exec api ls /mnt/media/music/`
8. ID3 tags readable (title, artist, thumbnail present)
9. POST playlist URL → multiple `pending` cards in UI
10. Cancel one pending download → 204, then GET → 404
11. POST discovery mode URL with limit=3 → 3 cards
12. Trigger an error (bad video ID) → status=error, error_message populated
13. Retry the error → status resets to pending, reruns
14. `docker compose restart api` mid-download → download resumes on startup

If all 14 steps pass, the project is in a good state.

---

## Common Issues & Fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| Download stays `pending` forever | Semaphore stuck or yt-dlp crashed silently | `docker compose logs api --tail 50` |
| Download goes straight to `error` | yt-dlp outdated or Deno missing | `docker compose exec api yt-dlp -U` then rebuild |
| "Never Gonna Give You Up" has wrong title | `--embed-metadata` flag missing from yt-dlp call | Check `services/downloader.py` yt-dlp flags |
| Playlist URL shows as `mode: track` instead of `mode: playlist` | `_is_playlist_url()` regex didn't match | Check URL format, must have `/playlist?` AND `list=` |
| Cancel button not visible on pending card | JS condition checking wrong field | Check `item.status === 'pending'` in `index.html` |
| UI stops updating even with active downloads | Smart polling stopped early | Check `hasActive` logic in polling code |
| `GET /api/library` returns empty after successful download | `_INSERT_MEDIA` failed silently | Check logs for SQLite errors |
