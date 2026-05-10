---
title: Library vs Offline Playback
type: concept
related: [architecture.md, ../progress/issues.md]
updated: 2026-05-08
---

# Library vs Offline Playback

Two distinct concepts that are easy to confuse.

---

## Library (web UI, issue #6)

The server-side catalog of all downloaded tracks. Accessible via the web UI when the browser has a connection to the Pi (Tailscale or local WiFi).

- Lives on the Pi (`media` table in SQLite)
- Browsable, filterable, searchable via `GET /api/library`
- Filtering is **server-side**: `?mood=energetic`, `?search=rick` are SQL queries on the Pi
- Supports: browse, filter by mood, search by title/artist, delete track
- **Requires Pi connectivity** — does not work offline

## Offline Playback (Syncthing + Poweramp, issues #9 + #11)

MP3 files and `.m3u` playlists synced from the Pi to the Android phone via Syncthing. Poweramp plays them from local storage.

- Lives on the phone (local filesystem)
- Synced once over WiFi, then fully offline
- **Does not require Pi connectivity after sync**

---

## Stream vs Download to Device (issue #6 feature)

Two ways to get audio from the Pi to a PC for playback:

### Stream
The Pi serves MP3 files over HTTP (`/media/music/filename.mp3`). Clicking Stream opens the file URL in a new browser tab — the browser or OS default player handles playback. **Pi must be reachable** (Tailscale).

### Download to Device
Same HTTP URL, but with a `download` attribute — the browser saves the MP3 to the local `Downloads` folder. Once saved, playable offline from the file manager with any media player. **Pi needed only at download time.**

Use Download to Device before a demo on a PC where the Pi may not be reachable, or where Tailscale connectivity is uncertain.

---

## Mood field in the Library

`media.mood` is NULL for all tracks until the ML pipeline (issue #7) is complete. The mood filter in the Library UI is built now but will return empty results until tracks are tagged. This is expected — the filter is built in advance of the data.

Valid mood values (after #7): `energetic`, `chill`, `sad`, `intense`.

After #8 is complete, every new download is automatically classified and `media.mood` is populated without user action.

## Genre field in the Library

`media.genre` is populated from yt-dlp metadata where available (YouTube Music official releases typically have genre tags). For tracks without metadata genre: KNN inference from audio similarity (#8). Manual override always available via Library UI dropdown + `PATCH /api/library/{id}`.

No second ML model is planned for genre classification.

---

## Playlist Diversity (issue #9 requirement)

Dynamic playlist generation (e.g. "give me 20 energetic tracks") must satisfy two constraints:

1. **No duplicates within one playlist** — the same track cannot appear twice in a single generated playlist. Simple deduplication during selection, not a DB-level constraint.
2. **Acoustic variety** — consecutive tracks should not sound too similar. Algorithm: **Maximal Marginal Relevance (MMR)** on audio feature vectors. Each next track maximises (mood match − λ × similarity to already-picked tracks). Prevents 5 near-identical dnb tracks appearing back-to-back in the same playlist.

Playlist length is controlled by the `limit` parameter in `POST /api/playlists/generate`. If fewer tracks exist than `limit`, returns all available.

.m3u files use **relative paths** (e.g. `../music/filename.mp3`) so the same file works on both the Pi (VLC) and the phone (Poweramp) after Syncthing sync, regardless of the absolute filesystem path on each device.

This is implemented in `services/playlist_generator.py` (issue #9), not in the ML model itself.
