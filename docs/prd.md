# PRD: MediaSync — Personal Media Sync System

## Problem Statement

As a mobile user who listens to music frequently, I do not want to pay for a YouTube Premium subscription just to listen to music offline or with the screen locked. I also want to avoid consuming mobile data when listening to music I already know I want. I collect YouTube and YouTube Music links throughout the day, but there is no convenient way to automatically download them, tag them by mood, and make them available offline on my phone without a streaming subscription.

## Solution

A Raspberry Pi 4 home server that accepts YouTube/YouTube Music links, downloads the audio, extracts mood features using a local ML model, generates dynamic playlists, and automatically syncs the files to my phone over WiFi via Syncthing. A simple web UI (accessible from any device via Tailscale) serves as the primary client for submitting links and browsing the library. Poweramp on Android plays the synced files.

## User Stories

1. As a user, I want to submit a YouTube or YouTube Music URL from any browser, so that the Pi downloads it automatically without me having to manage the process.
2. As a user, I want to submit a YouTube playlist URL, so that all tracks in the playlist are queued for download at once.
3. As a user, I want to see the status of each download in real time (pending, downloading, processing, done, error), so that I know what is happening.
4. As a user, I want the system to automatically extract audio from the YouTube video and convert it to MP3, so that it is playable in any music player.
5. As a user, I want the title, artist, and thumbnail to be automatically extracted from YouTube metadata and written to the MP3 ID3 tags, so that the file is properly identified in music players.
6. As a user, I want each downloaded track to be automatically classified by mood (energetic, chill, sad, intense) using a local ML model, so that I can generate playlists based on mood without manual tagging.
7. As a user, I want to browse my full music library in the web UI, so that I can see all downloaded tracks.
8. As a user, I want to filter the library by mood and search by title or artist, so that I can find specific tracks quickly.
9. As a user, I want to generate a playlist by mood (e.g. "give me 20 energetic tracks"), so that I have a ready-made playlist for working out, studying, or travelling.
10. As a user, I want the generated playlist to be saved as an .m3u file, so that I can open it directly in VLC (on desktop) or Poweramp (on Android).
11. As a user, I want to see the server health status in the web UI, so that I know the Pi is running and reachable.
12. As a user, I want to see storage usage and download statistics, so that I can monitor how much space the library takes up.
13. As a user, I want the Pi to be accessible from anywhere (school, work) via Tailscale, so that I can submit links and check status even when not on my home network.
14. As a user, I want downloaded files to be automatically synced to my phone via Syncthing over WiFi, so that music is available offline on my phone without manual transfer.
15. As a user, I want the sync to happen over WiFi only, so that it does not consume mobile data.
16. As a user, I want to delete a track from the library via the web UI, so that I can remove content I no longer want.
17. As a user, I want to cancel a pending or in-progress download, so that I can remove items I submitted by mistake.
18. As a user, I want to create manual playlists by selecting tracks from the library, so that I can curate my own collections beyond mood-based auto-playlists.
19. As a user, I want playlists to be automatically regenerated after every new download, so that mood-based playlists always reflect the current library.
20. As a user, I want the ML mood classification to run asynchronously after the download completes, so that the download pipeline is not blocked by inference time.

## Implementation Decisions

### Infrastructure
- Raspberry Pi 4 (4 GB RAM) running Raspberry Pi OS, Docker + docker-compose for service isolation
- VS Code Remote SSH as the development environment (developer connects from Windows via SSH)
- Tailscale installed on both the Pi and the developer's machines for remote access
- Public GitHub repository for code; wiki and docs live in the project folder and are backed up manually to Google Drive

### Modules

**`database.py`** — SQLite connection management and schema initialisation. Exposes a single async session factory used by all routers. Schema: `downloads`, `media`, `audio_features`, `playlists`, `playlist_items` tables as defined in CLAUDE.md.

**`services/downloader.py`** — Deep module. Wraps yt-dlp with Deno JS runtime (required for YouTube 2025+). Accepts a URL, validates it as YouTube/YouTube Music, starts an async background task, updates the `downloads` table at each stage (pending → downloading → processing → done/error), runs ffmpeg conversion to MP3 after download.

**`services/metadata.py`** — Reads title, artist, thumbnail, and upload date from yt-dlp output. Writes ID3 tags to the MP3 file using mutagen. No external metadata APIs (MusicBrainz removed from scope).

**`services/feature_extractor.py`** — Deep module. Uses librosa to extract a feature vector from a 30-second clip: MFCC (20 coefficients, mean + std), spectral centroid, spectral rolloff, zero crossing rate, chroma mean, tempo, energy. Returns a flat numpy array. Stores the result in the `audio_features` table as JSON.

**`services/classifier.py`** — Loads the mood TF Lite model (`models/mood_classifier.tflite`). Accepts a feature vector, runs inference, returns one of: `energetic`, `chill`, `sad`, `intense` with a confidence score. Updates the `media` table with the result.

**`services/playlist_generator.py`** — Deep module. Queries the `media` table filtered by mood and/or genre. Writes an `.m3u` file to `/mnt/media/playlists/`. Updates the `playlists` table. Called automatically after every completed download.

**`routers/downloads.py`** — `POST /api/downloads`, `GET /api/downloads`, `GET /api/downloads/{id}`, `DELETE /api/downloads/{id}`

**`routers/library.py`** — `GET /api/library` (with filters: mood, search), `GET /api/library/{id}`, `DELETE /api/library/{id}`

**`routers/playlists.py`** — `POST /api/playlists/generate`, `GET /api/playlists`, `POST /api/playlists`, `PUT /api/playlists/{id}`, `DELETE /api/playlists/{id}`

**`main.py`** — FastAPI app, CORS, static file serving from `static/`, `/api/health`, `/api/stats`

**`static/index.html`** — Single HTML file with vanilla JavaScript. Four views: link submission + queue, library browser, playlist manager, server stats. Served by FastAPI as a static file. No build step, no framework.

**`ml/mood_classification.ipynb`** — Google Colab notebook. Loads a custom dataset of ~25-30 tracks per mood category (energetic, chill, sad, intense). Extracts features with librosa. Trains a Keras Sequential model (Dense → Dropout → Dense → Dropout → softmax). Exports to TF Lite. The `.tflite` file is committed to the repo under `backend/models/`.

### Key Technical Constraints
- Pi 4 RAM: 4 GB — feature extraction and TF Lite inference must not hold large arrays in memory simultaneously
- yt-dlp requires Deno JS runtime for YouTube 2025+ — installed in the Docker image
- TF Lite inference uses `tflite-runtime` package, NOT full TensorFlow
- Media files are stored on an external USB SSD mounted at `/mnt/usb-ssd/media`, not the SD card
- Syncthing is configured as a separate Docker service; Pi side is send-only

### API Contracts
All endpoints return JSON. Download status values: `pending`, `downloading`, `processing`, `done`, `error`. Mood values: `energetic`, `chill`, `sad`, `intense`. Playlist type values: `auto`, `manual`.

## Testing Decisions

**What makes a good test:** Tests verify observable external behaviour — what the module returns or what side effects it produces — not internal implementation details. A test should still pass after an internal refactor.

**Modules to test:**

- **`services/downloader.py`** — mock yt-dlp subprocess calls; verify that the `downloads` table transitions through the correct status sequence; verify that an invalid URL returns a validation error; verify playlist URL expansion.
- **`routers/downloads.py`, `routers/library.py`, `routers/playlists.py`** — use FastAPI `TestClient`; verify HTTP status codes and response shapes for happy path and error cases (404 on missing ID, 422 on invalid input).

**Modules not tested (acceptable tradeoff given 3-4 week timeline):**
- `services/feature_extractor.py` — requires real audio files and librosa; not worth the fixture complexity
- `services/classifier.py` — requires the `.tflite` model file; not worth mocking the TF Lite interpreter
- `services/playlist_generator.py` — covered indirectly by the playlists router tests
- Web UI (`static/index.html`) — manual testing only

## Out of Scope

- **Android app** — replaced by web UI for the demo; Syncthing-Fork + Poweramp handle phone playback. Android app may be built after the demo deadline.
- **MusicBrainz integration** — removed; yt-dlp metadata is sufficient.
- **Last.fm genre enrichment** — removed from active scope.
- **Genre classification ML** — only mood classification is in scope. Genre can be added after demo if time permits.
- **Podcast transcription/summarization** — future extension documented in CLAUDE.md but not implemented.
- **ML-based playlist recommendations (cosine similarity)** — nice to have, deferred.
- **UI polish** — functional over beautiful; Material Design or any framework is not used.
- **Hilt / Jetpack Navigation / Android architecture components** — N/A (no Android app in scope).

## Further Notes

- **Demo setup:** Pi runs at home, accessible via Tailscale from the school laptop. The demo shows the full pipeline: submit link in web UI → Pi downloads and tags → `.m3u` generated → open in VLC on school laptop.
- **Timeline:** ~3-4 weeks remaining. Priority order: (1) infrastructure + download pipeline, (2) API + web UI, (3) ML pipeline + playlist generation, (4) Android app if time allows.
- **ML dataset:** User-built custom dataset; no GTZAN (poor Hungarian music coverage). 4 mood categories × ~25-30 tracks = ~100-120 tracks total.
- **Workflow:** Issues tracked in GitHub Issues + GitHub Projects (kanban). Wiki maintained in `wiki/` folder, read in Obsidian.
