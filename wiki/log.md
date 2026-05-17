# Log

## [2026-05-17] progress | #7 complete — mood_classifier.tflite deployed and verified on Pi

140 tracks labeled via Library UI (sad=1 removed → 3 classes: energetic=53, chill=48, intense=28). Feature extraction via `docker compose exec api python3 /tmp/extract_features.py` (130 rows). Colab training: Keras Sequential 128→64→3 softmax, 50 epochs, 61% test accuracy on 26 samples. `numpy<2` pinned in requirements.txt to fix tflite-runtime NumPy 2.x incompatibility. `mood_classifier.tflite` + `scaler_params.json` deployed to `backend/models/`. Smoke test OK — output shape [1 3]. Issue #7 closed.

## [2026-05-17] refactor | select_best_candidate — pure candidate filter/ranker extracted from search_and_download

`_is_suitable_candidate` + Topic-channel ranking összevonva publikus `select_best_candidate(candidates, blacklist_id) -> dict | None` pure functionbe (`services/downloader.py`). `search_and_download` ezt hívja a subprocess parse után.

`test_mix_downloader.py` újraírva: a 4 szűrési teszt (blacklist, duration, reject words, Topic preference) + 3 új eset (too long, all filtered, no Topic fallback) mostantól direkt `select_best_candidate`-et hívnak subprocess mock nélkül. Egyetlen subprocess-mock teszt maradt: a `search_and_download` RuntimeError path-je.

76/76 tests green.

## [2026-05-17] refactor | DownloadQueue service — mode routing extracted from HTTP layer

Created `backend/services/download_queue.py` as a deep module replacing the scattered logic in `routers/downloads.py` and `services/download_manager.py`.

**New module (`download_queue.py`):**
- `enqueue(url, mode, limit, db) -> list[DownloadRecord]` — URL validation, mode dispatch (mix/playlist/discovery/track), tracklist extraction, URL expansion, dedup, DB insert. Raises `InvalidURLError` (→ 422) or `DuplicateDownloadError` (→ 409).
- `execute_download(download_id)` — unified state machine: looks up record from DB (url, type, blacklist_id), dispatches to `search_and_download` (mix) or `run_download` (other), runs pending→downloading→processing→done/error transitions.
- `retry_interrupted()` — startup recovery; calls `execute_download` for all incomplete downloads (no more per-type dispatch).
- `DownloadRecord` Pydantic model moved here from router.

**Deleted:** `services/download_manager.py` (replaced entirely).

**Updated:** `routers/downloads.py` — `create_download` reduced from ~150 lines to ~15. `retry_download` simplified. **Updated:** `main.py` — imports `retry_interrupted` from `download_queue`. **Updated:** `database.py` — added `blacklist_id` column to `downloads` table (used by mix tracks in `execute_download`). **Updated:** `tests/test_downloads.py`, `tests/test_mix_mode.py` — patch paths changed to `services.download_queue.execute_download`.

73/73 tests green.

## [2026-05-17] feat | mode=mix implemented — TDD, 73 tests green

`POST /api/downloads` now supports `mode=mix`. Full implementation via TDD:

**New files:**
- `backend/services/mix_parser.py` — tracklist parser: normalize (en-dash, glued timestamps split on letter boundary), contiguous block detection (3+ matching lines, blank lines transparent), per-line processing (URL removal, slash-path strip, number prefix, timestamp+separator, emoji/bullet strip, trailing `[label]` strip), dedup by normalized key, sanity check (< 3 → `[]`).
- `backend/services/mix_extractor.py` — cascade orchestrator: yt-dlp `--dump-json` → chapters (if `"Artist - Title"` format, 3+) → description parse → best comment by tracklist-line score. `fetch_comments=True/False` parameter.
- `backend/tests/test_mix_parser.py` — 8 parser test cases (all spec cases)
- `backend/tests/test_mix_extractor.py` — 6 cascade tests
- `backend/tests/test_mix_downloader.py` — 10 search_and_download tests

**Modified files:**
- `backend/services/downloader.py` — added `search_and_download(query, blacklist_id, media_path)`: yt-dlp `ytsearch5:`, filter candidates (blacklist, duration 60-600s, reject words), prefer `- Topic` uploader, call `run_download`.
- `backend/routers/downloads.py` — added `mode=mix` branch in `create_download`: synchronous `extract_tracklist`, empty → 1 error record, per-track: insert pending + background `_process_mix_track`. Added `_process_mix_track` (same state machine as `_process_download`, calls `search_and_download`).
- `backend/pyproject.toml` — added `per-file-ignores: tests/* = ["E501"]` for long test data strings.

**Key bug fixed during TDD:** `_GLUED_TS_RE` initially used `(?<=\S)` which split `1:00:23` into `1:` + `\n00:23` (colon is `\S`). Fix: `(?<=[A-Za-z])` — only split when timestamp immediately follows a letter.

## [2026-05-17] decision | Mix download mode designed — mode=mix, 3-level cascade, search+download

Full design session for `mode=mix` in `POST /api/downloads`. Key decisions:

1. **Integration**: built into existing backend, not a separate microservice. Reuses `downloads` table, download manager, downloader.
2. **Cascade (3 levels, stops at first success)**: chapters → description → comments. Shazam fingerprinting is v1 out-of-scope (adds shazamio dep + minutes of processing time).
3. **Download strategy**: cascade extracts `"Artist - Title"` strings → `ytsearch5:` per track → pick best result (Topic channel preferred, 60–600s duration, no "sped up"/"nightcore"/etc.) → `run_download(url)`.
4. **Source video blacklist**: the original mix video ID is excluded from search results to prevent downloading the mix again instead of the individual track.
5. **Extraction timing**: synchronous (POST waits for cascade, max ~15s for comment fetch).
6. **Error cases**: no tracklist found → 1 error record with video title; track not found on YouTube → error record per track.
7. **Parser**: contiguous block detection (3+ consecutive tracklist-pattern lines), timestamp removal, number prefix stripping (safe for `2Pac`, `50 Cent`), emoji/bullet stripping, ` - ` separator requirement.

Implementation plan documented in `wiki/decisions/mix-download-mode.md`. New files: `mix_parser.py`, `mix_extractor.py`, `test_mix_parser.py`. Modified: `downloader.py`, `routers/downloads.py`, `download_manager.py`. No new dependencies.

## [2026-05-17] progress | #7 verification pass — AFK portion confirmed complete

Container smoke tests all green: librosa 0.10.2, feature_extractor import, tflite-runtime (ARM64 Coral repo wheel), API health. 46/46 pytest green. Ruff clean (3 E501 fixes in downloads.py + test_downloader.py). issues.md AC checkboxes updated. Remaining 2 HITL items: (1) label tracks via Library UI → run ml/extract_features.py → Colab → commit mood_classifier.tflite; (2) ml/smoke_test.py verification. Windows demo override (docker-compose.override.yml) conflicts with Pi volume on Pi — always run `docker compose -f docker-compose.yml` on Pi.

## [2026-05-17] feat | #7 ML pipeline AFK infrastructure implemented

All AFK work for issue #7 complete. User HITL steps remain (label tracks, run Colab, deploy model).

**Backend:**
- `PATCH /api/library/{id}` — accepts `{"mood": "energetic"|"chill"|"sad"|"intense"|null}`, returns updated `MediaItem`. 422 on unknown mood, 404 if track missing.
- `GET /api/library/export-csv` — returns `dataset_labels.csv` (only labeled tracks, `filename,mood` columns). Must be registered before `/{item_id}` route to avoid routing conflict.
- `backend/models/.gitkeep` — directory tracked, `.tflite` model added by user post-Colab.
- `backend/requirements.txt` — added `librosa==0.10.2`. `tflite-runtime` has no ARM64 PyPI wheel; Dockerfile installs via Google Coral repo with graceful fallback.

**Services:**
- `backend/services/feature_extractor.py` — extracts 57-float feature vector (MFCC 20×mean+std=40, spectral centroid, rolloff, ZCR, chroma 12, tempo, energy). 30s clip from 30s offset; falls back to 0s if track shorter than 30s.

**ML scripts:**
- `ml/extract_features.py` — standalone Pi script: reads `dataset_labels.csv` → extracts features → writes `dataset.csv` (f0..f56 + mood). Skips missing files with warning.
- `ml/mood_classification.ipynb` — Colab notebook: Drive mount → load dataset → StandardScaler → Keras Sequential (128→64→4 softmax) → 50 epochs → export `mood_classifier.tflite` + `scaler_params.json` → download both.
- `ml/smoke_test.py` — verify `mood_classifier.tflite` loads and runs zero-vector inference on Pi.

**Library UI:**
- Mood dropdown (`<select>`) on each track card; fires `PATCH /api/library/{id}` on change, pre-populates from existing mood.
- "Export training CSV" button in Library filter bar; direct `<a href download>` link.

**Label encoding (hardcoded):** `energetic=0, chill=1, sad=2, intense=3`

## [2026-05-11] fix | Playlist download mode implemented + multi-path yt-dlp crash fixed

Three bugs found and fixed during school demo session:

1. **Playlist mode not wired up** — `fetch_playlist_urls` existed in `downloader.py` but `create_download` had no `mode == "playlist"` branch. Added the branch: fetches individual track URLs via yt-dlp `--flat-playlist`, inserts each as a separate `downloads` record with per-track dedup. UI button re-enabled (was `disabled` with "Coming soon" label).

2. **yt-dlp multi-path crash** — When a pure playlist URL (no `v=`) was submitted in track mode, `--no-playlist` had no effect and yt-dlp downloaded all tracks, printing all file paths joined by newlines. `os.stat()` received the full multi-line string as a filename → `FileNotFoundError`. Fix: `stdout.decode().splitlines()[0].strip()` — take only the first path.

3. **Dedup check blocked playlist re-submission** — The top-level duplicate URL check (`WHERE url=? AND status != 'error'`) ran before playlist/discovery mode branching. After fix #2, the first track mode attempt succeeded and set the playlist URL to `done`, so re-submitting in playlist mode returned 409. Fix: moved the dedup check inside the track-only branch; playlist and discovery modes handle per-track dedup in their own loops.

4. **Discovery mode missing per-track dedup** — Same dedup logic was absent from the discovery branch. Added alongside the playlist fix.

**Issue #4 status corrected:** Was marked `done` but playlist mode was never actually connected. Now truly done.

**Local demo setup:** Added `docker-compose.override.yml` that replaces the Pi-specific bind mount (`/mnt/usb-ssd/media`) with `C:\tmp\mediasync-demo` for running the full stack (yt-dlp + ffmpeg + Deno) on Windows via Docker Desktop.

## [2026-05-11] decision | Issue #7 design session: dataset workflow, genre strategy, playlist diversity

Deep design discussion for #7 (ML mood pipeline). Key decisions:

1. **Success criterion**: "Play me energetic music" → system returns correctly tagged tracks. Mood classification is the primary ML output; genre is secondary.

2. **4 mood categories kept** (`energetic`, `chill`, `sad`, `intense`), expandable later. Acoustic features naturally separate into ~4-6 clusters — more categories hurt classifier confidence without improving UX.

3. **Genre strategy**: metadata-first (yt-dlp/YouTube Music provides structured genre tags for official releases). Fallback: KNN genre inference using cosine similarity on audio feature vectors (no second ML model). Manual override: Library UI dropdown + `PATCH /api/library/{id}`. Implemented in #8, not #7.

4. **Dataset labeling via Library UI (C approach)**: track cards get a mood dropdown (predefined labels, expandable). Saves via `PATCH /api/library/{id}`. "Export training CSV" button downloads `dataset_labels.csv` for Colab. Rule: if unsure in 5 seconds, skip — clean examples over noisy ones.

5. **Training workflow**: Pi feature extraction (`ml/extract_features.py`) → `dataset.csv` uploaded to Google Drive → Colab free tier CPU trains (seconds for ~120 samples, no GPU needed, no payment). MP3s never leave the Pi. The extract script reuses the same librosa code as production `services/feature_extractor.py`.

6. **Auto-classification of new downloads**: after model deployed, every new download triggers feature extraction + TF Lite inference → `media.mood` auto-populated. Implemented in #8.

7. **Playlist diversity (#9 requirement)**: MMR (Maximal Marginal Relevance) on audio feature vectors — consecutive tracks must not be acoustically too similar. No-repeat constraint via `last_played_at` in DB. Documented in `library-and-playback.md`.

## [2026-05-10] note | Deferred: long video track splitting

User wants to split long YouTube mix/compilation videos into individual tracks. Chapter-based approach (`yt-dlp --split-chapters`) was proposed but rejected — chapters are often missing, incorrectly defined, or bleed into each other. A more robust solution is needed (e.g. audio silence detection, spectral boundary detection, acoustic fingerprinting). Explicitly deferred until after core issues (#7–#11) are complete. Do not default to chapter-based splitting when this comes up.

## [2026-05-10] fix | Post-#6 bug fixes: DNS, tooltip, filename template, dedup, artist parse

Five bugs found during manual testing of issue #6, fixed TDD:

1. **Docker DNS** — Container couldn't resolve hostnames when Pi used phone hotspot instead of home router. Fix: added `dns: [8.8.8.8, 1.1.1.1]` to `api` service in `docker-compose.yml`. Container now resolves DNS regardless of upstream network source.

2. **Long title/artist truncation** — Track cards clipped long titles with no way to see the full text. Fix: added `title=` attribute to `.card-title` and `.card-artist` divs in `static/index.html` so the browser shows the full text on hover.

3. **Filename template** (TDD) — Regular YouTube downloads were using `%(artist)s - %(title)s.%(ext)s`, which resulted in filenames like `NFrealmusic - NF - When I Grow Up.mp3` because `%(artist)s` for regular YouTube = channel name, not artist. Fix: YouTube Music keeps `%(artist)s - %(title)s.%(ext)s`; regular YouTube uses `%(title)s.%(ext)s` only. 3 new tests in `test_downloader.py`.

4. **Duplicate URL submission** (TDD) — Same URL could be submitted multiple times. Fix: `create_download` checks `downloads` table for any non-error record with the same URL → 409 Conflict. Error-state URLs can be resubmitted (allows retry via new submit). 2 new tests in `test_downloads.py`.

5. **File path collision** (TDD) — Same YouTube + YouTube Music URLs for the same song would produce the same MP3 filename (after template fix) and create two media records. Fix: `_process_download` checks `media` table for existing `file_path` before INSERT — skips INSERT if file already tracked. 1 new test in `test_downloads.py`.

6. **Artist display** (TDD) — Library showed "NFrealmusic" (YouTube channel name) instead of "NF" (actual artist). Root cause: yt-dlp `%(artist)s` for regular YouTube = channel name. Fix: after reading ID3 tags, if URL is not YouTube Music, split title on ` - ` → `artist, title = parts`. 1 new test in `test_downloader.py`.

Note: old DB records downloaded before the fix still show the wrong artist — delete + re-download to get correct metadata.

**Rebuild required:** Python code changes need `docker compose up -d --build`, not just `docker compose up -d`.

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
