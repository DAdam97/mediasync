# Log

## [2026-05-08] feat | Library API + web UI (#6)

`GET /api/library` with `?mood=` and `?search=` server-side SQL filtering. `GET /api/library/{id}` single item, 404 if missing. `DELETE /api/library/{id}` removes DB record + MP3 file, soft-fails if file missing, 404 if record missing. `MediaItem` model: `duration_seconds` + `stream_url` added, raw `file_path` removed. `/media` StaticFiles mount added to `main.py` (serves MP3s at `/media/music/filename.mp3`). Library web UI: search bar (300ms debounce), mood dropdown, track cards with Stream/Download/Delete. `conftest.py` updated to use `importlib.reload(main)` — ensures StaticFiles picks up the correct `MEDIA_PATH` per test. 30 tests, all green.

Append-only chronological record of all work done on the project.
Format: `## [YYYY-MM-DD] type | short description`
Types: `feat` | `fix` | `decision` | `progress` | `note`

---

## [2026-05-08] docs | Expand manual test plan for issue #6 (Library API + file serving + web UI)

Added sections 12–14 to wiki/progress/manual-test-plan.md: Library API (list, filter, search, single, delete, soft-fail), file serving (stream, download, curl checks), Library web UI (empty state, track cards, mood filter, search, combined filter, delete). Regression run updated from 14 to 20 steps. Common Issues table extended with 3 new entries.

## [2026-05-08] decision | Issue #6 design: server-side filtering, stream/download-to-device, DELETE soft-fail

Grill session for #6 (Library API + web UI). Key decisions: (1) mood/search filtering is server-side (`?mood=`, `?search=` SQL queries on Pi, not client-side JS). (2) Library UI gets Stream button (HTTP link in new tab) and Download button (same URL with `download` attr) — Pi serves MP3s via HTTP static mount. Hybrid approach: stream for live demo, download-to-device for offline/uncertain-connectivity scenarios. (3) DELETE soft-fails on missing file — DB record always deleted, filesystem error silently ignored. (4) Track card fields: title, artist, duration_seconds, mood, Stream + Download buttons. Documented in wiki/concepts/library-and-playback.md.

## [2026-05-05] refactor | Architecture: config module, download manager service, queue writer

`config.py` introduced — `db_path()` and `media_path()` centralised from scattered `os.getenv` calls. `services/download_manager.py` extracted — download state machine (`process_download`) and startup recovery (`retry_interrupted`) moved out of the router. `_enqueue()` helper added to `routers/downloads.py` — the three INSERT+task branches (track/playlist/discovery) collapsed into one. `_run_yt_dlp_flat()` private helper added to `services/downloader.py` — subprocess duplication between `fetch_playlist_urls` and `fetch_related_urls` eliminated. 9 test patch targets updated (`routers.downloads._process_download` → `services.download_manager.process_download`). 25 tests, all green. Manual test plan written to `wiki/progress/manual-test-plan.md`.

## [2026-05-05] feat | Download pipeline: playlist URL expansion + cancel (#4)

`POST /api/downloads` auto-detects `youtube.com/playlist?list=` URLs and expands them into individual track records (one per track, `mode="playlist"`, `status="pending"`). `fetch_playlist_urls()` added to `downloader.py` (yt-dlp `--flat-playlist` on the playlist URL directly). `DELETE /api/downloads/{id}` added — cancels pending downloads only (404 for done/downloading/non-existent). 5 new tests, 25 total, all green.

## [2026-05-04] feat | Web UI: link submission + download queue (#5)

`static/index.html` fully wired: submit button calls `POST /api/downloads`, queue renders on load from `GET /api/downloads`, smart polling (3s interval, stops when no active downloads, restarts on next submit), form-level error display (422 invalid URL, network error), status badges colour-coded (yellow/blue/green/red), Enter key submits. All 16 backend tests still pass.

## [2026-05-04] feat | Download pipeline: single track + discovery mode (#3)

`POST /api/downloads` with URL validation (422 for non-YouTube), background asyncio task handling
`pending→downloading→processing→done` state machine, error_message on failure, media record on success.
`mode=discovery` queues N related tracks via YouTube Mix playlist (yt-dlp `--flat-playlist`).
`GET /api/downloads`, `GET /api/downloads/{id}`, `GET /api/library` added. 16 tests, all green.

## [2026-05-05] feat | DB schema + FastAPI skeleton + health endpoint (#2)

Backend scaffolded: requirements.txt, Dockerfile, docker-compose.yml, database.py (5 tables), main.py with /api/health and /api/stats endpoints, static/index.html placeholder UI, GitHub Actions CI workflow. TDD: 2 tests green (health + stats shape). Ruff passes. Mypy slow on first Pi run (stubs cache) — will pass in CI.

## [2026-05-04] progress | Pi infrastructure setup (partial — #1)

Docker installed and working. Tailscale installed and connected (Pi address: 100.115.50.112). /mnt/usb-ssd/media/ created with music/ and playlists/ subdirectories. Note: Pi boots from SSD (/dev/sda2, 223 GB) — no separate external drive, media path is a directory on the root SSD. VS Code Remote SSH pending (to be done from Windows tomorrow). Issue #1 remains open until SSH step is complete.

## [2026-05-01] progress | Initial planning session complete

Completed grill-me interview covering all major project decisions. PRD written to `docs/prd.md`. Wiki structure created. Key outcomes: web UI replaces Android app for demo, Tailscale for networking, mood-only ML (4 categories), MusicBrainz removed, ~3-4 week timeline confirmed. No code written yet.
