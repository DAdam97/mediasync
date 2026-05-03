---
title: Architecture
type: concept
related: [yt-dlp.md, tflite.md, syncthing.md]
updated: 2026-05-01
---

# Architecture

## System Overview

```
[Browser / Windows desktop]
        |
    Tailscale VPN
        |
[Raspberry Pi 4] ──── USB SSD (/mnt/usb-ssd/media/)
        |                    |
   FastAPI :8000        Syncthing :22000
        |                    |
   static/index.html    WiFi sync (send-only)
                             |
                      [Android phone]
                      Syncthing-Fork (receive-only)
                             |
                         Poweramp
```

## Components

### Raspberry Pi 4
- 4 GB RAM, Raspberry Pi OS
- All services run in Docker containers via docker-compose
- Media files on external USB SSD (not the SD card)
- Accessible remotely via Tailscale

### FastAPI Backend (`backend/`)
The core server. Handles:
- Download queue management (yt-dlp async tasks)
- Media library CRUD
- Playlist generation (.m3u files)
- ML inference orchestration (feature extraction → TF Lite classifier)
- Serves the static web UI from `static/index.html`

### Web UI (`static/index.html`)
Single HTML file with vanilla JavaScript. No build step. Four views:
- Link submission + download queue status
- Library browser (filter by mood, search by title/artist)
- Playlist manager (generate by mood, view, delete)
- Server stats (storage, download counts)

### Syncthing
Runs as a separate Docker service. Pi side is configured send-only. Phone (Android) runs Syncthing-Fork, configured receive-only, WiFi-only. Syncthing watches `/mnt/media/` and pushes changes to the phone automatically.

### Poweramp (Android)
Not part of this project. Opens `.m3u` files from the Syncthing-synced folder. No custom Android app is built — Poweramp handles all playback.

## Data Flow

1. User submits YouTube URL in web UI
2. FastAPI creates a `downloads` record (status: `pending`)
3. Background asyncio task starts yt-dlp download (status: `downloading`)
4. After download: ffmpeg converts to MP3, mutagen writes ID3 tags (status: `processing`)
5. librosa extracts audio features, stored in `audio_features` table
6. TF Lite mood classifier runs, result stored in `media` table
7. Playlist generator regenerates mood-based `.m3u` files
8. File moved to `/mnt/media/music/` (status: `done`)
9. Syncthing detects the new file and syncs to phone over WiFi

## File Layout on Pi

```
/mnt/usb-ssd/media/         ← USB SSD mount point
├── music/
│   └── Artist - Title.mp3
├── playlists/
│   ├── auto_energetic.m3u
│   ├── auto_chill.m3u
│   ├── auto_sad.m3u
│   ├── auto_intense.m3u
│   └── user_*.m3u
└── metadata.db             ← SQLite database
```

## Tech Stack Summary

| Layer | Technology |
|---|---|
| Backend framework | FastAPI + Uvicorn |
| Database | SQLite |
| Download | yt-dlp + ffmpeg + Deno |
| Audio features | librosa |
| ML inference | TF Lite (`tflite-runtime`) |
| Metadata | mutagen (ID3 tags) |
| File sync | Syncthing |
| Networking | Tailscale |
| Containerisation | Docker + docker-compose |
| CI/CD | GitHub Actions (Ruff + mypy + pytest) |
