# MediaSync — Personal Media Sync System

## Project Summary

A personal media sync system that saves mobile data. The user collects YouTube / YouTube Music links on their phone, sends them to a Raspberry Pi 4 home server, which downloads the media, processes it with AI (genre/mood tagging), and automatically syncs it back to the phone over WiFi. Music playback is handled by Poweramp via .m3u playlist files.

**Current status:** Planning phase — no code yet. Restarting with structured workflow: grill-me → PRD → issues → kanban → implementation.

---

## Architecture Overview

```
┌─────────────────┐         REST API           ┌──────────────────────┐
│   Android App   │ ◄──────(Retrofit)────────► │   Raspberry Pi 4     │
│   (Kotlin)      │                            │   (FastAPI backend)  │
│                 │                            │                      │
│ • Link submit   │   ◄── Syncthing (WiFi) ──► │ • yt-dlp download    │
│ • Status view   │        (file sync)         │ • TF Lite tagging    │
│ • Playlist      │                            │ • Playlist generation│
│   generation    │                            │ • SQLite database    │
│ • Library       │                            │ • Syncthing server   │
│   browsing      │                            │                      │
│                 │                            │                      │
│ Poweramp ◄──────┤ .m3u files                 │                      │
│ (playback)      │                            │                      │
└─────────────────┘                            └──────────────────────┘
```

**3 main components:**
1. **Android app (Kotlin)** — Link collection, library management, playlist UI
2. **Raspberry Pi 4 backend (FastAPI + Python)** — Downloading, AI processing, API server, file management
3. **Syncthing** — Automatic WiFi-based file synchronization (no custom code needed)

---

## Tech Stack

| Component | Technology | Version/Notes |
|---|---|---|
| **Backend framework** | FastAPI + Uvicorn | Async, auto-generated Swagger docs |
| **Database** | SQLite | Simple, zero-config, sufficient for single-user |
| **Download** | yt-dlp + ffmpeg | YouTube + YouTube Music links. + Deno JS runtime (required for YouTube 2025+) |
| **Audio feature extraction** | librosa | MFCC, mel spectrogram, chroma features |
| **ML classification** | Keras → TF Lite | Training in Colab, TF Lite inference on Pi |
| **Metadata handling** | mutagen | ID3 tag read/write |
| **File sync** | Syncthing | Pi: send-only, phone: receive-only |
| **Android HTTP client** | Retrofit 2 + Gson | Type-safe REST API communication |
| **Android background tasks** | WorkManager | WiFi-only constraint, survives app kill |
| **Containerization** | Docker + docker-compose | Services running on Pi |
| **CI/CD** | GitHub Actions | Lint (Ruff), type check (mypy), pytest |
| **Testing** | pytest + Espresso | Backend + Android tests |

---

## Features in Detail

### 1. Link Collection & Download Management (CORE — Weeks 1-3)

**Android app UI:**
- Simple input field for pasting YouTube / YouTube Music URLs
- Android Share Intent receiver (share from other apps → MediaSync)
- Download queue display with statuses: `pending`, `downloading`, `processing`, `done`, `error`
- Playlist links expand to show all tracks underneath

**Backend (FastAPI) endpoints:**

```
POST /api/downloads          — Submit a new link for download
GET  /api/downloads          — Query download queue (filter by status)
GET  /api/downloads/{id}     — Get details of a single download
DELETE /api/downloads/{id}   — Cancel/delete a download

GET  /api/library            — List full media library (filter, search, paginate)
GET  /api/library/{id}       — Get details of a media item (metadata, tags)
DELETE /api/library/{id}     — Delete a media item

POST /api/playlists/generate — Generate playlist by mood/genre
GET  /api/playlists          — List available playlists
POST /api/playlists          — Create manual playlist
PUT  /api/playlists/{id}     — Edit a playlist
DELETE /api/playlists/{id}   — Delete a playlist

GET  /api/health             — Server status (app checks if Pi is reachable)
GET  /api/stats              — Storage usage, download statistics
```

**Download logic on the Pi:**
1. URL arrives → validated as YouTube / YouTube Music (`youtube.com`, `youtu.be`, `music.youtube.com`)
2. Background task (asyncio) starts the yt-dlp download
3. After download: ffmpeg conversion if needed (e.g. opus → mp3)
4. Metadata extraction: yt-dlp provides title/artist/album/thumbnail/release date. YouTube Music "topic" channels have clean structured metadata; regular YouTube titles may need "Artist - Title" parsing. MusicBrainz API called best-effort for supplementary data (never blocks the pipeline).
5. ID3 tag writing (mutagen)
6. File moved to Syncthing shared folder
7. Status updated in database

**Genre/mood tags come exclusively from the ML pipeline** (librosa feature extraction → TF Lite classifier), run asynchronously after the download completes. No external source is used for genre/mood.

**File organization on the Pi:**
```
/mnt/media/
├── music/
│   ├── Artist - Title.mp3
│   └── ...
├── playlists/
│   ├── auto_energetic.m3u
│   ├── auto_chill.m3u
│   ├── user_workout.m3u
│   └── ...
└── metadata.db                    (SQLite database)
```

### 2. WiFi Synchronization (CORE — Week 4)

**Syncthing configuration:**
- Pi side: `/mnt/media/` folder → send-only
- Android side: Syncthing-Fork app → receive-only, WiFi-only sync setting
- Phone folder (e.g. `/sdcard/MediaSync/`) → Poweramp auto-discovers it

**Android app WiFi detection:**
- `ConnectivityManager` + `NetworkCapabilities.TRANSPORT_WIFI` monitoring
- OR simpler: periodic ping to FastAPI `/api/health` endpoint
- WorkManager `NetworkType.UNMETERED` constraint → syncs in background

### 3. Genre & Mood Tagging (AI FEATURE — Week 6)

**Training (in Google Colab):**
1. Load dataset (custom-built or GTZAN as baseline — see ML section below)
2. librosa feature extraction: MFCC (13-40 coefficients), mel spectrogram, spectral contrast, chroma
3. Keras Sequential model:
   ```
   Input (feature vector) → Dense(256, relu) → Dropout(0.3) → Dense(128, relu) → Dropout(0.3) → Dense(N, softmax)
   ```
   OR 1D CNN on spectrograms
4. Training + validation (80/20 split)
5. Model export: `tf.lite.TFLiteConverter.from_keras_model(model)` → `.tflite` file

**Inference (on Raspberry Pi):**
1. Downloaded track → librosa feature extraction (2-5 sec / 30 sec clip)
2. TF Lite interpreter loads the `.tflite` model
3. Prediction → genre label + confidence score
4. Result written to ID3 tag (mutagen) + database

**Mood classification:**
- Same pipeline, but trained on Valence-Arousal model
- 4 categories: energetic (high arousal, high valence), sad (low arousal, low valence), calm (low arousal, high valence), angry/intense (high arousal, low valence)
- Or K-Means clustering on feature vectors → automatic mood groups

### 4. Playlist Generation (AI FEATURE — Week 6)

**Automatic playlists:**
- The system generates .m3u files based on tagged music:
  - `auto_energetic.m3u` — high energy/tempo tracks
  - `auto_chill.m3u` — calm tracks
  - `auto_sad.m3u` — melancholic mood
  - Per-genre as well: `auto_rock.m3u`, `auto_hiphop.m3u` etc.
- Regenerated after every new download

**Manual playlist + ML recommendation:**
- User creates a playlist in the app (e.g. "Workout")
- Adds a few tracks manually
- System uses cosine similarity to find tracks with similar feature vectors from the library
- Suggests: "These tracks are similar, should I add them?"

**API-based generation:**
- `POST /api/playlists/generate` body: `{"mood": "energetic", "genre": "rap", "limit": 20}`
- Pi filters the media library based on requested parameters
- Returns the playlist + generates .m3u file
- App opens the generated .m3u in Poweramp

### 5. Library Browsing (CORE — Week 5)

**Android app UI:**
- Library tab: list all downloaded media
- Filters: genre, mood, date
- Search: by title, artist
- Playlist view: automatic + manual playlists
- Music playback: one tap opens Poweramp with the selected track/playlist (Intent)

---

## Future Extensions (not in current scope)

The architecture is designed to easily accommodate these features later:

### Podcast Transcription & Summarization
- **Download:** Same download pipeline, routed to `podcasts/` subfolder
- **Transcription:** Faster-Whisper (CTranslate2) with `tiny.en` or `base.en` model — ARM optimized for Pi 4
- **Summarization:** Sumy LexRank/LSA extractive summarization from transcript
- **Storage:** `.txt` (transcript) + `.json` (summary + keywords) alongside audio file
- **Integration points:**
  - Add `media_type = 'podcast'` to media table (column already exists)
  - Add `transcript_path` and `summary` fields (columns already exist)
  - New `services/transcriber.py` and `services/summarizer.py`
  - New Android screen for podcast episode list + summary display
  - New router `routers/podcasts.py`

---

## Database Schema (SQLite)

```sql
-- Download queue
CREATE TABLE downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    source TEXT NOT NULL,              -- 'youtube' (YouTube / YouTube Music)
    type TEXT NOT NULL,                -- 'track', 'playlist'
    status TEXT DEFAULT 'pending',     -- 'pending', 'downloading', 'processing', 'done', 'error'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Media library
CREATE TABLE media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    artist TEXT,
    album TEXT,
    duration_seconds INTEGER,
    file_path TEXT NOT NULL,            -- relative path from /mnt/media/
    file_size_bytes INTEGER,
    media_type TEXT NOT NULL DEFAULT 'music',  -- 'music' (future: 'podcast')
    source_url TEXT,
    download_id INTEGER REFERENCES downloads(id),

    -- AI-generated fields
    genre TEXT,                         -- ML classification result
    genre_confidence REAL,
    mood TEXT,                          -- 'energetic', 'calm', 'sad', 'intense'
    mood_confidence REAL,

    -- Reserved for future podcast extension
    transcript_path TEXT,               -- podcast transcript file path
    summary TEXT,                       -- podcast summary text

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP                 -- when synced to phone
);

-- Audio features (for ML)
CREATE TABLE audio_features (
    media_id INTEGER PRIMARY KEY REFERENCES media(id),
    mfcc_mean TEXT,                     -- JSON array: 13-40 values
    mfcc_std TEXT,
    spectral_centroid REAL,
    spectral_rolloff REAL,
    zero_crossing_rate REAL,
    chroma_mean TEXT,                   -- JSON array
    tempo REAL,
    energy REAL,
    feature_vector TEXT                 -- full feature vector JSON (for cosine similarity)
);

-- Playlists
CREATE TABLE playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,                 -- 'auto', 'manual'
    filter_criteria TEXT,               -- JSON: {"mood": "energetic", "genre": "rock"}
    m3u_path TEXT,                      -- generated .m3u file path
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Playlist items
CREATE TABLE playlist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER REFERENCES playlists(id) ON DELETE CASCADE,
    media_id INTEGER REFERENCES media(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Codebase Structure

```
mediasync/
├── CLAUDE.md                          # <-- THIS FILE
├── README.md
├── docs/
│   ├── decisions/                     # Architecture Decision Records (ADR)
│   │   ├── 001-fastapi-over-flask.md
│   │   ├── 002-syncthing-for-filesync.md
│   │   ├── 003-tflite-for-edge-inference.md
│   │   └── ...
│   ├── diagrams/                      # UML diagrams (Mermaid)
│   ├── devlog.md                      # Development log
│   └── ai-usage-log.md               # AI tool usage documentation
│
├── backend/                           # Raspberry Pi backend
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                        # FastAPI app entry point
│   ├── config.py                      # Settings (paths, model sizes, etc.)
│   ├── database.py                    # SQLite connection + schema
│   ├── routers/
│   │   ├── downloads.py               # /api/downloads endpoints
│   │   ├── library.py                 # /api/library endpoints
│   │   └── playlists.py               # /api/playlists endpoints
│   ├── services/
│   │   ├── downloader.py              # yt-dlp wrapper + Spotify→YouTube resolver
│   │   ├── metadata.py                # ID3 tag handling (mutagen)
│   │   ├── classifier.py              # TF Lite inference (genre + mood)
│   │   ├── feature_extractor.py       # librosa audio feature extraction
│   │   └── playlist_generator.py      # Playlist generation + .m3u export
│   ├── models/                        # TF Lite models (.tflite files)
│   │   ├── genre_classifier.tflite
│   │   └── mood_classifier.tflite
│   └── tests/
│       ├── test_downloader.py
│       ├── test_classifier.py
│       └── ...
│
├── ml/                                # ML training (Google Colab notebooks)
│   ├── genre_classification.ipynb
│   ├── mood_classification.ipynb
│   └── data/                          # Dataset (in .gitignore)
│
├── android/                           # Android app (Kotlin)
│   └── MediaSync/
│       ├── app/
│       │   └── src/main/
│       │       ├── java/.../mediasync/
│       │       │   ├── MainActivity.kt
│       │       │   ├── data/
│       │       │   │   ├── api/
│       │       │   │   │   ├── MediaSyncApi.kt        # Retrofit interface
│       │       │   │   │   └── ApiClient.kt
│       │       │   │   ├── models/                     # Data classes
│       │       │   │   └── repository/                 # Repository pattern
│       │       │   ├── ui/
│       │       │   │   ├── downloads/                  # Download manager screen
│       │       │   │   ├── library/                    # Library browser
│       │       │   │   └── playlists/                  # Playlist manager
│       │       │   └── workers/
│       │       │       └── SyncWorker.kt               # WorkManager WiFi sync
│       │       └── res/
│       └── build.gradle.kts
│
├── docker-compose.yml                 # Services running on Pi
├── .github/
│   └── workflows/
│       ├── backend-ci.yml             # Python lint + test
│       └── android-ci.yml             # Android build + test
└── .gitignore
```

---

## Docker Compose (Raspberry Pi)

```yaml
version: "3.8"
services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - media_data:/mnt/media
      - ./backend/models:/app/models
    environment:
      - MEDIA_PATH=/mnt/media
      - DATABASE_PATH=/mnt/media/metadata.db
    restart: unless-stopped

  syncthing:
    image: syncthing/syncthing:latest
    ports:
      - "8384:8384"   # Web UI
      - "22000:22000"  # Sync protocol
    volumes:
      - media_data:/mnt/media
      - syncthing_config:/var/syncthing/config
    restart: unless-stopped

volumes:
  media_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/usb-ssd/media    # External USB SSD!
  syncthing_config:
```

---

## Development Schedule (8 weeks)

### Priorities (if time runs short)
- **MUST HAVE (minimum for grade):** Link submission → download → sync → Poweramp playback + basic library UI
- **SHOULD HAVE:** Genre/mood ML tagging + automatic playlist generation
- **NICE TO HAVE:** ML-based playlist recommendations (cosine similarity), polished UI

### Week 1 — Foundation 
- [ ] Create git repo, .gitignore, README
- [ ] Docker + docker-compose setup on Pi
- [ ] FastAPI skeleton: health endpoint, CORS, project structure
- [ ] SQLite schema initialization
- [ ] GitHub Actions CI pipeline (Ruff lint + mypy + pytest)
- [ ] First ADRs (tech stack decisions)
- [ ] Architecture diagram (Mermaid)

### Week 2 — Download Engine 
- [ ] yt-dlp wrapper service (single track + playlist)
- [ ] URL validation (YouTube / YouTube Music only)
- [ ] MusicBrainz API call for supplementary metadata (best-effort)
- [ ] Download queue management (async background tasks)
- [ ] `/api/downloads` CRUD endpoints
- [ ] Tests for download logic

### Week 3 — Library Management
- [ ] File organization logic (music/ folder structure)
- [ ] Metadata extraction + ID3 tag writing (mutagen)
- [ ] `/api/library` endpoints (listing, filtering, search)
- [ ] Storage monitoring (`/api/stats`)
- [ ] Tests

### Week 4 — Android MVP + Syncthing 
- [ ] Android project setup (Kotlin, Gradle)
- [ ] Retrofit API client (`MediaSyncApi.kt`)
- [ ] Link submission screen (+ Share Intent receiver)
- [ ] Download queue display
- [ ] Syncthing configuration (Pi: send-only, phone: receive-only)
- [ ] WorkManager-based WiFi detection
- **➡️ DEMO-READY MVP: link submit → download → sync → Poweramp playback**

### Week 5 — Android Features
- [ ] Library browser screen (filters, search)
- [ ] Playlist manager UI (manual creation, editing)
- [ ] Poweramp integration (open .m3u via Intent)
- [ ] Basic UI polish

### Week 6 — AI Pipeline 
- [ ] librosa feature extraction service
- [ ] Custom dataset: user-defined genre categories, 50-100 tracks/genre, 30-sec clips (Option B — no GTZAN)
- [ ] Keras model training in Colab (genre + mood)
- [ ] TF Lite conversion + deployment to Pi
- [ ] Classifier service (inference)
- [ ] Automatic playlist generation
- [ ] Playlist generation UI in Android app

### Week 7 — Testing & Documentation
- [ ] Backend unit test completion (target: >80% coverage)
- [ ] Android UI tests (Espresso)
- [ ] Performance benchmarks (classifier accuracy, sync time)
- [ ] Write project documentation (architecture, implementation, testing)
- [ ] Finalize UML diagrams

### Week 8 — Wrap Up
- [ ] Finalize project documentation
- [ ] Prepare presentation slides
- [ ] Demo rehearsal (live demo practice)
- [ ] Code cleanup, finalize README
- [ ] Last bugfixes

---

## Development Conventions

### Python (backend)
- **Formatter:** Ruff (`ruff format`)
- **Linter:** Ruff (`ruff check`)
- **Type checking:** mypy (strict mode)
- **Testing:** pytest + pytest-asyncio
- **Python version:** 3.11+
- **Async:** asyncio (FastAPI natively supports it)
- **Code language:** All code, comments, docstrings, and variable names in English

### Kotlin (Android)
- **Min SDK:** 26 (Android 8.0)
- **Architecture:** MVVM + Repository pattern
- **DI:** Hilt (if time permits) or manual injection
- **Navigation:** Jetpack Navigation Component
- **UI:** Material Design 3 + View Binding
- **Code language:** All code, comments, and variable names in English

### Git Conventions
- **Branch strategy:** `main` (stable) + `develop` + feature branches (`feature/download-engine`)
- **Commit messages:** Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- **PRs:** Every feature branch merges to develop via PR

### Documentation
- **ADR format:** MADR v4.0 (`docs/decisions/`)
- **Diagrams:** Mermaid (`.mermaid` files in `docs/diagrams/`)
- **Development log:** `docs/devlog.md` — weekly entries
- **AI usage log:** `docs/ai-usage-log.md` — documenting Claude Code usage

---

## Notes for Claude Code

### General Rules
- All code, variable names, comments, and docstrings must be in English
- UI strings in the Android app: Hungarian
- README and docs: English
- Always KISS (Keep It Simple) — don't over-engineer, there are 8 weeks
- Backend code lives in `backend/`, Android code in `android/`, ML notebooks in `ml/`

### Backend Specific
- Pi 4 has 4 GB RAM — watch memory usage
- Media files are on external USB SSD, not the SD card
- yt-dlp needs Deno as JS runtime (2025+ YouTube requirement)
- TF Lite: use `tflite-runtime` package, NOT full tensorflow
- Keep services modular — each service in its own file under `services/`

### Android Specific
- Poweramp integration: generate `.m3u` files + open via Intent
- Do NOT build a custom music player — Poweramp handles playback
- WiFi-only sync: WorkManager `NetworkType.UNMETERED` constraint
- Share Intent: allow sending links directly from other apps

### ML Specific
- Training: Google Colab (GPU) — Keras Sequential or 1D CNN
- Deploy: TF Lite conversion (`tf.lite.TFLiteConverter`)
- On Pi: `tflite-runtime` — lightweight inference only
- Audio features: librosa MFCC, mel spectrogram, spectral features
- Dataset: CUSTOM-BUILT ONLY — user-defined genre categories, 50-100 tracks per genre, 30-sec clips. No GTZAN (poor Hungarian music coverage). Genre/mood tags come 100% from audio ML — no external source is reliable for this.
- MusicBrainz: best-effort supplementary metadata only, never block the pipeline on it

---

## External Services & APIs

| Service | Purpose | API Key? |
|---|---|---|
| YouTube (yt-dlp) | Audio download (YouTube + YouTube Music) | No (but rate limited) |
| MusicBrainz | Supplementary metadata (best-effort) | No (open database) |
| Last.fm | Genre tags, similar artists (optional enrichment) | Yes (free API key) |

---

## Legal Note

This project is for personal use only. Hungarian copyright law (Act LXXVI of 1999, §35) permits private copying for natural persons. The system does not include sharing/distribution features.


---

## LLM Wiki

The wiki lives in `wiki/` inside this project folder. Claude Code writes and maintains it; the user reads it in Obsidian. The project folder (including the wiki) is manually backed up to Google Drive by the user as needed.

All wiki pages are written in English.

### Directory structure

```
wiki/
├── index.md              ← list of all pages with one-line descriptions (always read this first)
├── log.md                ← append-only chronological log of all work done
├── concepts/
│   ├── architecture.md   ← system overview, components, data flow
│   ├── yt-dlp.md         ← how yt-dlp is used, known limitations
│   ├── tflite.md         ← ML pipeline, TF Lite inference on Pi
│   └── syncthing.md      ← file sync setup and configuration
├── decisions/
│   ├── web-ui-over-android.md
│   ├── tailscale-networking.md
│   └── mood-only-ml.md
└── progress/
    ├── week1.md
    └── week2.md
```

### Development workflow

The project follows this workflow:
1. **Planning:** `grill-me` → `to-prd` → `to-issues` → GitHub Projects kanban board
2. **Implementation:** Pick issue from kanban → implement → update wiki → close issue
3. **Tracking:** GitHub Issues + GitHub Projects (kanban view) for task management

### Every session start

1. Read `wiki/index.md` for orientation
2. Read the last 5 entries of `wiki/log.md` for recent context
3. Check GitHub Issues for the current sprint's open tasks

### After completing any task

1. Update the relevant wiki page(s)
2. Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] type | short description
   ```
   where type = `feat` | `fix` | `decision` | `progress` | `note`
3. Update `wiki/index.md` if a new page was created
4. Close or update the corresponding GitHub Issue

### Page frontmatter (required on every wiki page)

```
---
title:
type: concept | decision | progress
related: []
updated: YYYY-MM-DD
---
```
