---
title: Planning Phase
type: progress
related: []
updated: 2026-05-01
---

# Planning Phase (2026-05-01)

## Status

Planning complete. No code written yet. PRD published to `docs/prd.md`.

## What Was Decided

### Architecture
- Raspberry Pi 4 (4 GB RAM, fresh Raspberry Pi OS) is the server
- Docker + docker-compose for all services
- VS Code Remote SSH as development environment (Windows → Pi via SSH)
- Tailscale for remote access from school/work
- Public GitHub repository for code
- Wiki in `wiki/` folder, manually backed up to Google Drive

### Client Strategy
- Web UI (single `index.html` + vanilla JS, served by FastAPI) is the primary client
- Web UI used for: demo at school, daily use on Windows desktop
- Android app deferred to after the demo deadline
- Syncthing-Fork + Poweramp handle phone playback (no custom Android app needed)
- VLC opens generated `.m3u` files during the demo

### Backend
- FastAPI + SQLite
- yt-dlp + ffmpeg + Deno for downloads
- mutagen for ID3 tags
- No MusicBrainz (removed — yt-dlp metadata is sufficient)
- No Last.fm (removed from active scope)

### ML Pipeline
- Mood classification only (energetic, chill, sad, intense)
- ~25-30 tracks per category, custom dataset (not GTZAN)
- librosa feature extraction → Keras → TF Lite → `tflite-runtime` on Pi
- Genre classification deferred to after the demo

### Testing
- `services/downloader.py` — unit tests with mocked yt-dlp subprocess
- API endpoints (`routers/`) — FastAPI TestClient integration tests
- Other modules: no tests (acceptable tradeoff given timeline)

## Timeline

~3-4 weeks remaining until demo deadline (exact date TBD).

Priority order:
1. Infrastructure (Pi setup, Docker, Tailscale, GitHub, VS Code Remote SSH)
2. Download pipeline (yt-dlp wrapper, async queue, metadata, DB)
3. API layer + Web UI
4. ML pipeline (feature extraction, Colab training, TF Lite deployment)
5. Playlist generation
6. Android app (after demo, if time allows)

## Open Items

- GitHub repo not yet created — needs to be done before first commit
- Exact demo date not confirmed with teacher
- ML dataset collection not started (user needs to build ~100-120 track dataset)
