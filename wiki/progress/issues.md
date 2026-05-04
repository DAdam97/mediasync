---
title: GitHub Issues — All Slices
type: progress
related: [planning.md]
updated: 2026-05-05
---

# GitHub Issues

All vertical slices for the MediaSync project. Tracked at: https://github.com/DAdam97/mediasync/issues

Update the Status column and `updated` date whenever an issue is closed.

## Issue Map

| # | Title | Type | Status | Blocked by |
|---|---|---|---|---|
| [#1](https://github.com/DAdam97/mediasync/issues/1) | Pi infrastructure setup | HITL | open | — |
| [#2](https://github.com/DAdam97/mediasync/issues/2) | Database schema + FastAPI skeleton + health endpoint | AFK | done | #1 |
| [#3](https://github.com/DAdam97/mediasync/issues/3) | Download pipeline: single track (yt-dlp → MP3 → ID3 tags → DB) | AFK | done | #2 |
| [#4](https://github.com/DAdam97/mediasync/issues/4) | Download pipeline: YouTube playlist URL expansion | AFK | open | #3 |
| [#5](https://github.com/DAdam97/mediasync/issues/5) | Web UI: link submission + download queue view | AFK | done | #3 |
| [#6](https://github.com/DAdam97/mediasync/issues/6) | Library API + web UI: browse, filter by mood, search, delete | AFK | open | #3 |
| [#7](https://github.com/DAdam97/mediasync/issues/7) | ML pipeline: dataset collection + Colab training + TF Lite deployment | HITL | open | #3 |
| [#8](https://github.com/DAdam97/mediasync/issues/8) | Mood classifier inference on Pi (async, post-download) | AFK | open | #7 |
| [#9](https://github.com/DAdam97/mediasync/issues/9) | Playlist generation: mood-based .m3u files + API | AFK | open | #8 |
| [#10](https://github.com/DAdam97/mediasync/issues/10) | Web UI: playlist manager + server stats view | AFK | open | #9 |
| [#11](https://github.com/DAdam97/mediasync/issues/11) | Syncthing setup: Pi send-only + phone receive-only WiFi sync | HITL | open | #1 |

## Dependency Graph

```
#1 Pi infrastructure (HITL)
├── #2 DB + FastAPI skeleton
│   └── #3 Download pipeline (single track)
│       ├── #4 Playlist URL expansion
│       ├── #5 Web UI: submit + queue
│       ├── #6 Library API + web UI
│       └── #7 ML pipeline (HITL: dataset + Colab)
│           └── #8 Mood inference on Pi
│               └── #9 Playlist generation
│                   └── #10 Web UI: playlists + stats
└── #11 Syncthing setup (HITL)
```

---

## Issue Details

### #1 — Pi infrastructure setup (HITL)

**What to build:** Set up the Raspberry Pi 4 as a fully operational development and production server. End-to-end: a developer on Windows can open VS Code, connect to the Pi via Remote SSH, edit files, and reach the Pi from any network via Tailscale.

**Acceptance criteria:**
- [x] Docker and docker-compose installed and working on the Pi
- [x] Tailscale installed and connected on Pi + developer laptop(s)
- [ ] Pi reachable at its Tailscale address from a non-home network
- [ ] VS Code Remote SSH configured — developer can open the project folder from Windows
- [x] GitHub repo cloned on Pi at working path
- [x] `/mnt/usb-ssd/media/` mounted and writable (external USB SSD)
- [x] `music/` and `playlists/` subdirectories created under media root

**Notes:** Pi boots from SSD (/dev/sda2, 223 GB) — no separate external drive, `/mnt/usb-ssd/media/` is a directory on the root SSD. Tailscale IP: `100.115.50.112`.

**Pending:** VS Code Remote SSH (from Windows) + Tailscale non-home network test — to be done next session before closing this issue.

---

### #2 — Database schema + FastAPI skeleton + health endpoint

**What to build:** Bootstrap the backend: SQLite schema initialisation, FastAPI app wired up, `/api/health` and `/api/stats` endpoints returning real data. End-to-end: `docker-compose up` starts the API container, browser hits `http://pi:8000/api/health` and gets a JSON response, `/docs` Swagger UI is accessible.

**Acceptance criteria:**
- [x] `docker-compose.yml` defines the `api` service (and `syncthing` stub)
- [x] `database.py` creates all five tables on startup (`downloads`, `media`, `audio_features`, `playlists`, `playlist_items`)
- [x] `GET /api/health` returns `{"status": "ok"}`
- [x] `GET /api/stats` returns storage usage and download counts (even if zero)
- [x] FastAPI serves `static/index.html` as a placeholder page
- [x] `requirements.txt` and `Dockerfile` are complete
- [x] Ruff + mypy pass in CI (GitHub Actions workflow created)

---

### #3 — Download pipeline: single track (yt-dlp → MP3 → ID3 tags → DB)

**What to build:** A user submits a single YouTube or YouTube Music URL. The Pi downloads the audio, converts it to MP3, writes ID3 tags (title, artist, thumbnail), moves the file to `/mnt/media/music/`, and records the result in the database. End-to-end: POST a URL → poll GET status → transitions `pending → downloading → processing → done` → MP3 appears with correct ID3 tags.

**Acceptance criteria:**
- [x] `POST /api/downloads` accepts a YouTube/YouTube Music URL and returns a download record
- [x] Invalid URLs (non-YouTube) are rejected with HTTP 422
- [x] Background asyncio task runs yt-dlp with Deno runtime
- [x] ffmpeg converts the downloaded audio to MP3
- [x] mutagen writes title, artist, and thumbnail (APIC) to the MP3
- [x] `downloads` table status transitions correctly through all stages
- [x] On error, `downloads.error_message` is populated and status is `error`
- [x] `media` table record created with file path and metadata on success
- [x] Tests: URL validation, status transitions (mocked yt-dlp subprocess)

**Extra (added in this session):**
- [x] `mode=discovery`: fetches YouTube Mix playlist related URLs, queues each as separate download
- [x] `limit` parameter controls how many discovery tracks are queued

---

### #4 — Download pipeline: YouTube playlist URL expansion

**What to build:** A user submits a YouTube playlist URL. The Pi expands it into individual tracks and queues each one as a separate download record. End-to-end: POST a playlist URL → API returns list of created download IDs (one per track) → each track downloads independently.

**Acceptance criteria:**
- [ ] `POST /api/downloads` accepts playlist URLs (`?list=...`)
- [ ] yt-dlp extracts all track URLs from the playlist
- [ ] Each track creates its own `downloads` record
- [ ] Response includes all created download IDs
- [ ] `DELETE /api/downloads/{id}` cancels a pending download
- [ ] Tests: playlist URL expansion (mocked yt-dlp), cancel pending download

---

### #5 — Web UI: link submission + download queue view

**What to build:** The web UI lets a user paste a YouTube URL, submit it for download, and see the live status of all downloads. End-to-end: paste URL → click submit → download card appears → status updates from `pending` to `done` without page refresh.

**Acceptance criteria:**
- [x] `static/index.html` has a URL input field and submit button
- [x] Submitting a URL calls `POST /api/downloads` and shows the new item in the queue
- [x] Queue view shows all downloads with their current status
- [x] Status updates automatically (smart polling: 3s interval, stops when idle, restarts on submit)
- [x] Error state is displayed clearly (invalid URL → 422, download failed → error badge)
- [x] Playlist URLs show all expanded tracks in the queue (list response rendered as multiple cards)
- [x] No JavaScript framework — vanilla JS + fetch API only

---

### #6 — Library API + web UI: browse, filter by mood, search, delete

**What to build:** A user can browse all downloaded tracks in the web UI, filter by mood, search by title/artist, and delete tracks. End-to-end: Library tab → track cards → search/filter → delete removes track from library and filesystem.

**Acceptance criteria:**
- [ ] `GET /api/library` returns all media items with optional `?mood=` and `?search=` query params
- [ ] `GET /api/library/{id}` returns a single media item
- [ ] `DELETE /api/library/{id}` removes the DB record and the MP3 file from disk
- [ ] Web UI Library tab displays all tracks
- [ ] Mood filter buttons filter the list client-side
- [ ] Search input filters by title/artist client-side
- [ ] Tests: GET list with filters, GET single, DELETE (HTTP status codes + response shapes)

---

### #7 — ML pipeline: dataset collection + Colab training + TF Lite deployment (HITL)

**What to build:** Build and train a mood classification model in Google Colab, export it as TF Lite, deploy to the Pi. Dataset must be collected manually. End-to-end: ~100 tracks across 4 moods → Colab training → `mood_classifier.tflite` committed to repo → model loads on Pi without errors.

**Acceptance criteria:**
- [ ] Custom dataset built: ~25-30 tracks × 4 moods (energetic, chill, sad, intense)
- [ ] `ml/mood_classification.ipynb` extracts features with librosa (MFCC, spectral, chroma, tempo, energy)
- [ ] Keras Sequential model trained with 80/20 train/val split
- [ ] Model accuracy documented in the notebook
- [ ] Model exported as `backend/models/mood_classifier.tflite`
- [ ] `tflite-runtime` installed in the Docker image
- [ ] Model loads and runs inference on the Pi without errors (smoke test)

---

### #8 — Mood classifier inference on Pi (async, post-download)

**What to build:** After a track finishes downloading, the Pi automatically extracts audio features and runs TF Lite mood inference. Result stored in DB and track tagged with mood label. End-to-end: download completes → `GET /api/library/{id}` returns `mood: "energetic"`.

**Acceptance criteria:**
- [ ] `services/feature_extractor.py` extracts feature vector from a 30-second clip (starting at 30s)
- [ ] Feature vector stored as JSON in `audio_features` table
- [ ] `services/classifier.py` loads `mood_classifier.tflite` and runs inference
- [ ] `media.mood` and `media.mood_confidence` updated after inference
- [ ] Inference runs asynchronously — does not block the download status response
- [ ] If model file is missing, inference is skipped gracefully (mood stays null)

---

### #9 — Playlist generation: mood-based .m3u files + API

**What to build:** The Pi automatically generates mood-based .m3u playlist files after every completed download. End-to-end: download completes → `auto_energetic.m3u` etc. regenerated in `/mnt/media/playlists/` → open in VLC → tracks play correctly.

**Acceptance criteria:**
- [ ] `services/playlist_generator.py` generates one .m3u file per mood containing all tagged tracks
- [ ] Playlists regenerated automatically after every download completes
- [ ] `POST /api/playlists/generate` accepts `{"mood": "energetic", "limit": 20}` and returns a playlist
- [ ] `GET /api/playlists` lists all available playlists
- [ ] `POST /api/playlists` creates a manual playlist
- [ ] `DELETE /api/playlists/{id}` deletes a playlist and its .m3u file
- [ ] .m3u files are valid and openable in VLC
- [ ] Tests: playlist API endpoints (HTTP status + response shape)

---

### #10 — Web UI: playlist manager + server stats view

**What to build:** The web UI shows available playlists and lets the user generate new mood-based playlists. A stats view shows storage usage and download counts. End-to-end: Playlists tab → see auto-generated playlists → Generate → select mood → new playlist appears → .m3u download link.

**Acceptance criteria:**
- [ ] Playlists tab lists all playlists from `GET /api/playlists`
- [ ] "Generate playlist" form lets user pick mood and limit
- [ ] Generated playlist appears in the list immediately
- [ ] Each playlist has a download link for the .m3u file
- [ ] Stats view shows total tracks, storage used, downloads by status
- [ ] Server health indicator visible on all views (green/red dot)

---

### #11 — Syncthing setup: Pi send-only + phone receive-only WiFi sync (HITL)

**What to build:** Configure Syncthing so that completed downloads automatically sync from Pi to Android phone over WiFi. Pure Syncthing configuration, no custom code. End-to-end: download on Pi → connect phone to home WiFi → MP3 appears on phone → Poweramp plays it.

**Acceptance criteria:**
- [ ] Syncthing Docker service running on Pi (web UI accessible at :8384)
- [ ] Pi folder `/mnt/media/` configured as send-only
- [ ] Syncthing-Fork installed on Android phone
- [ ] Phone folder configured as receive-only, WiFi-only
- [ ] Pi and phone paired (device ID exchange done)
- [ ] A test file syncs successfully from Pi to phone
- [ ] .m3u playlist files sync alongside MP3 files
- [ ] Poweramp scans the synced folder and plays tracks

---

## How to Update This File

When an issue is closed:
1. Change its Status from `open` to `done`
2. Check off completed acceptance criteria
3. Update the `updated` date in the frontmatter
4. Add a log entry in `wiki/log.md`
